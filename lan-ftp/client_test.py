import argparse
import configparser
import os
from ftplib import FTP


def load_default_config():
    cfg = configparser.ConfigParser()
    if os.path.exists("config.ini"):
        cfg.read("config.ini", encoding="utf-8")
    return cfg


def main():
    parser = argparse.ArgumentParser(description="简单 FTP 上传/下载测试脚本")
    parser.add_argument("--host", default=None, help="FTP 服务器地址")
    parser.add_argument("--port", type=int, default=None, help="FTP 端口")
    parser.add_argument("--user", default="anonymous", help="用户名")
    parser.add_argument("--password", default="", help="密码")
    parser.add_argument("--upload", default="test_upload.txt", help="本地上传文件路径")
    parser.add_argument("--download", default="test_download.txt", help="下载到本地的文件路径")
    args = parser.parse_args()

    cfg = load_default_config()
    host = args.host or cfg.get("server", "lan_ip", fallback="auto")
    port = args.port or cfg.getint("server", "listen_port", fallback=2121)

    if host == "auto":
        # 兼容未填写的情况，允许用户直接输入
        host = "127.0.0.1"

    # 准备上传文件
    if not os.path.exists(args.upload):
        with open(args.upload, "w", encoding="utf-8") as f:
            f.write("LAN FTP 测试文件\n")

    ftp = FTP()
    ftp.connect(host, port, timeout=10)
    ftp.login(args.user, args.password)

    # 上传
    with open(args.upload, "rb") as f:
        ftp.storbinary(f"STOR {os.path.basename(args.upload)}", f)

    # 下载
    with open(args.download, "wb") as f:
        ftp.retrbinary(f"RETR {os.path.basename(args.upload)}", f.write)

    ftp.quit()
    print("上传/下载测试完成")


if __name__ == "__main__":
    main()
