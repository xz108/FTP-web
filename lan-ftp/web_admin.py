import base64
import configparser
import os
import time
from typing import Dict, Any

from flask import Flask, Response, request, redirect


def _basic_auth_ok(user: str, password: str) -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        u, p = raw.split(":", 1)
        return u == user and p == password
    except Exception:
        return False


def _auth_challenge() -> Response:
    return Response("需要登录", 401, {"WWW-Authenticate": "Basic realm=LAN-FTP"})


def create_app(state: Dict[str, Any], authorizer, cfg_path: str, web_user: str, web_pass: str) -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _check_auth():
        if not web_user:
            return None
        if _basic_auth_ok(web_user, web_pass):
            return None
        return _auth_challenge()

    @app.get("/")
    def index():
        with state["lock"]:
            clients = list(state["clients"].values())
            logs = list(state["logs"])[-50:]
            start_time = state["start_time"]
            lan_ip = state["lan_ip"]
            port = state["listen_port"]
            root_dir = state["root_dir"]
            anon = state["anon_enable"]

        up_seconds = int(time.time() - start_time)

        html = [
            "<html><head><meta charset='utf-8'>",
            "<title>LAN FTP 管理</title>",
            "<style>",
            "body{font-family:Arial,Helvetica,sans-serif;padding:20px;background:#f6f7fb;}",
            ".card{background:#fff;border-radius:10px;padding:16px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);} ",
            "table{width:100%;border-collapse:collapse;}th,td{padding:8px;border-bottom:1px solid #eee;text-align:left;}",
            ".muted{color:#666;font-size:12px;}",
            "input{padding:6px;}button{padding:6px 10px;}",
            "</style></head><body>",
            f"<h2>LAN FTP 管理面板</h2>",
            f"<div class='card'><b>状态</b><br>",
            f"局域网地址: <code>ftp://{lan_ip}:{port}/</code><br>",
            f"根目录: <code>{root_dir}</code><br>",
            f"匿名登录: {'允许' if anon else '禁用'}<br>",
            f"运行时间: {up_seconds}s<br>",
            "</div>",
            "<div class='card'><b>在线连接</b>",
            "<table><tr><th>IP</th><th>用户名</th><th>连接时间</th></tr>",
        ]
        for c in clients:
            html.append(
                f"<tr><td>{c['ip']}</td><td>{c.get('username') or '-'}</td><td>{time.strftime('%H:%M:%S', time.localtime(c['connected_at']))}</td></tr>"
            )
        html.append("</table></div>")

        html.append("<div class='card'><b>添加用户</b><br>")
        html.append(
            "<form method='post' action='/add_user'>"
            "用户名: <input name='username' required> "
            "密码: <input name='password' required> "
            "权限: <input name='perm' value='elradfmwMT'> "
            "目录: <input name='home' placeholder='留空使用根目录'> "
            "<button type='submit'>添加</button>"
            "</form>"
        )
        html.append("<div class='muted'>说明: 仅添加到 users.ini，并立即生效。</div></div>")

        html.append("<div class='card'><b>最近日志</b><br><pre>")
        html.append("\n".join(logs) if logs else "无日志")
        html.append("</pre></div>")

        html.append("</body></html>")
        return "".join(html)

    @app.post("/add_user")
    def add_user():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        perm = request.form.get("perm", "elradfmwMT").strip() or "elradfmwMT"
        home = request.form.get("home", "").strip()

        if not username or not password:
            return Response("用户名和密码不能为空", 400)

        # 写入 users.ini
        ucfg = configparser.ConfigParser()
        if os.path.exists(state["users_file"]):
            ucfg.read(state["users_file"], encoding="utf-8-sig")
        if not ucfg.has_section(username):
            ucfg.add_section(username)
        ucfg.set(username, "password", password)
        ucfg.set(username, "perm", perm)
        if home:
            ucfg.set(username, "home", home)

        with open(state["users_file"], "w", encoding="utf-8") as f:
            ucfg.write(f)

        # 立即生效
        try:
            if not home:
                home = state["root_dir"]
            authorizer.add_user(username, password, home, perm=perm)
        except Exception:
            pass

        return redirect("/")

    return app
