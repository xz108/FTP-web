from __future__ import annotations

import mimetypes
import os
import secrets
import shutil
import socket
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

import qrcode
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config

APP_ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(APP_ROOT / "templates"))

app = FastAPI(title="LAN File Share")
app.mount("/static", StaticFiles(directory=str(APP_ROOT / "static")), name="static")

_sessions: dict[str, str] = {}


# ----------------------------
# Utilities
# ----------------------------

def ensure_root() -> None:
    config.ROOT_DIR.mkdir(parents=True, exist_ok=True)


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def safe_resolve(rel_path: str) -> Path:
    rel_path = rel_path.strip().lstrip("/")
    target = (config.ROOT_DIR / rel_path).resolve()
    if not target.is_relative_to(config.ROOT_DIR):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target


def format_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def build_breadcrumbs(rel_path: str) -> List[Tuple[str, str]]:
    parts = [p for p in rel_path.split("/") if p]
    breadcrumbs: List[Tuple[str, str]] = [("根目录", "")]
    acc: List[str] = []
    for part in parts:
        acc.append(part)
        breadcrumbs.append((part, "/".join(acc)))
    return breadcrumbs


def guess_type(path: Path) -> str:
    if path.is_dir():
        return "folder"
    mime, _ = mimetypes.guess_type(str(path))
    if mime:
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("text/"):
            return "text"
    return "file"


def normalize_rel_filename(name: str) -> str:
    name = name.replace("\\", "/")
    name = name.lstrip("/")
    return name


def ensure_no_sep(name: str) -> None:
    if "/" in name or "\\" in name or name.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid name")


def is_authed(request: Request) -> bool:
    if not config.AUTH_ENABLED:
        return True
    token = request.cookies.get(config.SESSION_COOKIE)
    return bool(token and token in _sessions)


def require_auth(request: Request) -> None:
    if not is_authed(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ----------------------------
# Startup
# ----------------------------

@app.on_event("startup")
async def startup_event() -> None:
    ensure_root()
    lan_ip = get_lan_ip()
    url = f"http://{lan_ip}:{config.LAN_PORT}"
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    print("\nLAN File Share 已启动")
    print(f"访问地址: {url}")
    print("二维码(ASCII):")
    try:
        qr.print_ascii(invert=True)
    except Exception:
        print("二维码生成失败，可忽略。")
    try:
        img_path = APP_ROOT / "static" / "qr.png"
        qr.make_image(fill_color="black", back_color="white").save(img_path)
        print(f"二维码图片: {img_path}")
    except Exception:
        pass


# ----------------------------
# Auth
# ----------------------------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not config.AUTH_ENABLED:
        return RedirectResponse("/", status_code=302)
    return TEMPLATES.TemplateResponse(
        "login.html", {"request": request, "error": ""}
    )


@app.post("/login")
async def login_action(request: Request, username: str = Form(...), password: str = Form(...)):
    if not config.AUTH_ENABLED:
        return RedirectResponse("/", status_code=302)
    if username != config.ADMIN_USER or password != config.ADMIN_PASSWORD:
        return TEMPLATES.TemplateResponse(
            "login.html", {"request": request, "error": "用户名或密码错误"}
        )
    token = secrets.token_urlsafe(24)
    _sessions[token] = username
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(config.SESSION_COOKIE, token, httponly=True)
    return resp


@app.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(config.SESSION_COOKIE)
    if token:
        _sessions.pop(token, None)
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp


# ----------------------------
# Pages
# ----------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, path: str = ""):
    if config.AUTH_ENABLED and not is_authed(request):
        return RedirectResponse("/login", status_code=302)
    rel_path = path.strip().lstrip("/")
    abs_path = safe_resolve(rel_path) if rel_path else config.ROOT_DIR
    if not abs_path.exists() or not abs_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")

    items = []
    for entry in abs_path.iterdir():
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "rel": ("/".join([p for p in [rel_path, entry.name] if p])).lstrip("/"),
                "is_dir": entry.is_dir(),
                "size": "-" if entry.is_dir() else format_size(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "type": guess_type(entry),
            }
        )

    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    return TEMPLATES.TemplateResponse(
        "index.html",
        {
            "request": request,
            "items": items,
            "breadcrumbs": build_breadcrumbs(rel_path),
            "current_path": rel_path,
            "auth_enabled": config.AUTH_ENABLED,
        },
    )


# ----------------------------
# File Actions
# ----------------------------

@app.post("/upload")
async def upload(
    request: Request,
    path: str = Form(""),
    files: List[UploadFile] = File(...),
    _=Depends(require_auth),
):
    rel_path = path.strip().lstrip("/")
    target_dir = safe_resolve(rel_path) if rel_path else config.ROOT_DIR
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Target folder not found")

    for up in files:
        rel_name = normalize_rel_filename(up.filename)
        dest = (target_dir / rel_name).resolve()
        if not dest.is_relative_to(config.ROOT_DIR):
            raise HTTPException(status_code=400, detail="Invalid file path")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            while True:
                chunk = await up.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

    return JSONResponse({"ok": True})


@app.get("/download")
async def download(path: str, _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists() or abs_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        abs_path,
        filename=abs_path.name,
    )


@app.get("/file")
async def file_inline(path: str, _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists() or abs_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(abs_path)


def zip_dir_to_temp(dir_path: Path) -> Path:
    fd, base_path = tempfile.mkstemp()
    os.close(fd)
    os.unlink(base_path)
    zip_base = Path(base_path)
    zip_path = zip_base.with_suffix(".zip")
    shutil.make_archive(str(zip_base), "zip", dir_path)
    return zip_path


def cleanup_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


@app.get("/download-zip")
async def download_zip(path: str, background: BackgroundTasks, _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists() or not abs_path.is_dir():
        raise HTTPException(status_code=404, detail="Folder not found")
    zip_path = zip_dir_to_temp(abs_path)
    background.add_task(cleanup_file, zip_path)
    return FileResponse(zip_path, filename=f"{abs_path.name}.zip")


@app.post("/delete")
async def delete(path: str = Form(""), _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    if rel_path == "":
        raise HTTPException(status_code=400, detail="Cannot delete root")
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    if abs_path.is_dir():
        shutil.rmtree(abs_path)
    else:
        abs_path.unlink()
    return JSONResponse({"ok": True})


@app.post("/rename")
async def rename(path: str = Form(""), new_name: str = Form(""), _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    ensure_no_sep(new_name)
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    dest = abs_path.parent / new_name
    if dest.exists():
        raise HTTPException(status_code=400, detail="Target exists")
    abs_path.rename(dest)
    return JSONResponse({"ok": True})


@app.post("/mkdir")
async def mkdir(path: str = Form(""), name: str = Form(""), _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    ensure_no_sep(name)
    abs_path = safe_resolve(rel_path) if rel_path else config.ROOT_DIR
    target = abs_path / name
    if target.exists():
        raise HTTPException(status_code=400, detail="Folder exists")
    target.mkdir(parents=True, exist_ok=False)
    return JSONResponse({"ok": True})


@app.get("/text-preview")
async def text_preview(path: str, _=Depends(require_auth)):
    rel_path = path.strip().lstrip("/")
    abs_path = safe_resolve(rel_path)
    if not abs_path.exists() or abs_path.is_dir():
        raise HTTPException(status_code=404, detail="Not found")
    max_bytes = config.MAX_TEXT_PREVIEW_KB * 1024
    try:
        with abs_path.open("rb") as f:
            data = f.read(max_bytes)
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = "无法预览该文件"
    return PlainTextResponse(text)


@app.get("/health")
async def health():
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.LAN_HOST,
        port=config.LAN_PORT,
        reload=False,
        log_level="info",
    )
