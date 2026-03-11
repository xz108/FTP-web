import configparser
import ipaddress
import os
import socket
import sys
import threading
import time
from collections import deque
from typing import List, Optional

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import qrcode
from web_admin import create_app

STATE = {
    "clients": {},
    "logs": deque(maxlen=200),
    "lock": threading.Lock(),
    "start_time": time.time(),
    "lan_ip": "",
    "listen_port": 0,
    "root_dir": "",
    "anon_enable": True,
    "users_file": "",
}


def load_config(path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if not os.path.exists(path):
        print(f"配置文件不存在: {path}")
        sys.exit(1)
    # 兼容 UTF-8 BOM 文件
    cfg.read(path, encoding="utf-8-sig")
    return cfg


def get_candidates_from_hostname() -> List[str]:
    ips = []
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None)
        for info in infos:
            ip = info[4][0]
            ips.append(ip)
    except Exception:
        pass
    return ips


def get_candidate_from_udp() -> Optional[str]:
    # 不需要真正连通外网，仅用于让系统选择默认网卡
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def pick_best_lan_ip(candidates: List[str]) -> str:
    def score(ip: str) -> int:
        try:
            obj = ipaddress.ip_address(ip)
            if obj.version != 4:
                return -1
            if ip.startswith("192.168."):
                return 300
            if ip.startswith("10."):
                return 250
            if obj in ipaddress.ip_network("172.16.0.0/12"):
                return 200
            if obj.is_private:
                return 100
            return 10
        except Exception:
            return -1

    best_ip = "127.0.0.1"
    best_score = -1
    for ip in candidates:
        if ip.startswith("127."):
            continue
        s = score(ip)
        if s > best_score:
            best_score = s
            best_ip = ip
    return best_ip


def get_lan_ip() -> str:
    candidates = []
    udp_ip = get_candidate_from_udp()
    if udp_ip:
        candidates.append(udp_ip)
    candidates.extend(get_candidates_from_hostname())
    return pick_best_lan_ip(candidates)


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def parse_users_inline(cfg: configparser.ConfigParser, root_dir: str) -> List[dict]:
    users = []
    if not cfg.has_section("users"):
        return users
    for key, value in cfg.items("users"):
        if key == "users_file":
            continue
        # 格式：password, perm, home(可选)
        parts = [p.strip() for p in value.split(",")]
        if len(parts) < 1:
            continue
        password = parts[0]
        perm = parts[1] if len(parts) >= 2 and parts[1] else "elradfmwMT"
        home = parts[2] if len(parts) >= 3 and parts[2] else root_dir
        users.append({"username": key, "password": password, "perm": perm, "home": home})
    return users


def parse_users_file(path: str, root_dir: str) -> List[dict]:
    users = []
    if not path:
        return users
    if not os.path.exists(path):
        return users
    ucfg = configparser.ConfigParser()
    # 兼容 UTF-8 BOM 文件
    ucfg.read(path, encoding="utf-8-sig")
    for section in ucfg.sections():
        password = ucfg.get(section, "password", fallback="")
        perm = ucfg.get(section, "perm", fallback="elradfmwMT")
        home = ucfg.get(section, "home", fallback=root_dir)
        if not password:
            continue
        users.append({"username": section, "password": password, "perm": perm, "home": home})
    return users


def print_qr(text: str) -> None:
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(text)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("二维码生成失败，可忽略。")


class ManagedHandler(FTPHandler):
    # 记录连接信息，用于 Web 管理页面展示
    def on_connect(self):
        super().on_connect()
        with STATE["lock"]:
            STATE["clients"][id(self)] = {
                "ip": self.remote_ip,
                "username": None,
                "connected_at": time.time(),
            }
            STATE["logs"].append(f"[CONNECT] {self.remote_ip}")

    def on_login(self, username):
        super().on_login(username)
        with STATE["lock"]:
            if id(self) in STATE["clients"]:
                STATE["clients"][id(self)]["username"] = username
            STATE["logs"].append(f"[LOGIN] {self.remote_ip} -> {username}")

    def on_disconnect(self):
        super().on_disconnect()
        with STATE["lock"]:
            STATE["clients"].pop(id(self), None)
            STATE["logs"].append(f"[DISCONNECT] {self.remote_ip}")

    def log(self, msg):
        # 收集日志，避免输出过多
        with STATE["lock"]:
            STATE["logs"].append(f"[FTP] {msg}")


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(base_dir, "config.ini")
    cfg = load_config(cfg_path)

    # 读取配置
    root_dir = cfg.get("server", "root_dir", fallback="FTP-Share")
    if not os.path.isabs(root_dir):
        root_dir = os.path.join(base_dir, root_dir)

    listen_host = cfg.get("server", "listen_host", fallback="0.0.0.0")
    listen_port = cfg.getint("server", "listen_port", fallback=2121)
    pasv_min = cfg.getint("server", "pasv_min_port", fallback=2122)
    pasv_max = cfg.getint("server", "pasv_max_port", fallback=2150)
    lan_ip_cfg = cfg.get("server", "lan_ip", fallback="auto").strip()
    max_cons = cfg.getint("server", "max_cons", fallback=50)
    max_cons_per_ip = cfg.getint("server", "max_cons_per_ip", fallback=5)
    idle_timeout = cfg.getint("server", "idle_timeout", fallback=300)

    anon_enable = cfg.getboolean("anonymous", "enable", fallback=True)
    anon_perm = cfg.get("anonymous", "perm", fallback="elradfmwMT")

    users_file = cfg.get("users", "users_file", fallback="users.ini") if cfg.has_section("users") else "users.ini"
    users_file_path = os.path.join(base_dir, users_file) if users_file else ""

    # Web 管理配置
    web_enable = cfg.getboolean("web", "enable", fallback=True)
    web_host = cfg.get("web", "host", fallback="0.0.0.0")
    web_port = cfg.getint("web", "port", fallback=8080)
    web_user = cfg.get("web", "username", fallback="admin")
    web_pass = cfg.get("web", "password", fallback="admin")

    # 目录准备
    ensure_dir(root_dir)

    # 自动获取局域网IP
    lan_ip = get_lan_ip() if lan_ip_cfg.lower() == "auto" else lan_ip_cfg

    # 配置权限
    authorizer = DummyAuthorizer()
    if anon_enable:
        authorizer.add_anonymous(root_dir, perm=anon_perm)

    for user in parse_users_inline(cfg, root_dir):
        authorizer.add_user(user["username"], user["password"], user["home"], perm=user["perm"])

    for user in parse_users_file(users_file_path, root_dir):
        authorizer.add_user(user["username"], user["password"], user["home"], perm=user["perm"])

    # 处理器
    handler = ManagedHandler
    handler.authorizer = authorizer
    handler.passive_ports = range(pasv_min, pasv_max + 1)
    handler.masquerade_address = lan_ip
    handler.timeout = idle_timeout

    # 初始化状态
    STATE["lan_ip"] = lan_ip
    STATE["listen_port"] = listen_port
    STATE["root_dir"] = root_dir
    STATE["anon_enable"] = anon_enable
    STATE["users_file"] = users_file_path

    # 启动服务器
    try:
        server = FTPServer((listen_host, listen_port), handler)
        server.max_cons = max_cons
        server.max_cons_per_ip = max_cons_per_ip

        # 启动 Web 管理页面
        if web_enable:
            app = create_app(STATE, authorizer, cfg_path, web_user, web_pass)
            t = threading.Thread(
                target=app.run,
                kwargs={"host": web_host, "port": web_port, "debug": False, "use_reloader": False},
                daemon=True,
            )
            t.start()

        print("\n=== LAN FTP 服务器已启动 ===")
        print(f"根目录: {root_dir}")
        print(f"监听: {listen_host}:{listen_port}")
        print(f"局域网地址: {lan_ip}:{listen_port}")
        print(f"被动端口: {pasv_min}-{pasv_max}")
        if web_enable:
            print(f"Web 管理: http://{lan_ip}:{web_port} (账号: {web_user})")

        if anon_enable:
            print("匿名登录: 允许（用户名 anonymous，密码留空）")
        else:
            print("匿名登录: 禁用")

        print("\n连接二维码（匿名）：")
        print_qr(f"ftp://{lan_ip}:{listen_port}/")

        server.serve_forever()
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or e.errno in (98, 48):
            print("端口被占用，请修改 config.ini 中的 listen_port。")
        elif e.errno == 13:
            print("没有权限绑定端口或访问目录，请检查权限。")
        else:
            print(f"启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n服务器已停止。")


if __name__ == "__main__":
    main()
