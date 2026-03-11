# LAN File Share（局域网 Web 文件分享）

一个纯局域网使用的轻量 Web 文件分享工具，支持文件/文件夹上传下载、拖拽、多文件、进度条、预览、二维码访问、可选登录。

## 功能亮点

- 仅局域网使用：默认绑定 `0.0.0.0`
- 浏览/上传/下载/删除/重命名/新建文件夹
- 支持文件夹上传（浏览器支持 `webkitdirectory`）
- 文件夹下载自动打包成 zip
- 大文件流式上传/下载
- 响应式 UI，支持暗黑模式
- 启动后打印局域网访问地址 + ASCII 二维码，并生成 `static/qr.png`
- 可选登录认证（默认 `admin / 123456`）

## 目录结构

```
lan-file-share/
├── main.py
├── config.py
├── requirements.txt
├── static/
│   ├── app.js
│   └── styles.css
├── templates/
│   ├── index.html
│   └── login.html
├── README.md
└── .env.example
```

## 安装

建议使用 Python 3.11+。

```
cd lan-file-share
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行

```
python main.py
```

启动后终端会显示类似：

```
访问地址: http://192.168.1.100:8000
二维码(ASCII):
```

手机/电脑同一局域网内打开该地址即可使用。

## 配置

复制 `.env.example` 为 `.env` 并按需修改：

- `LAN_HOST`：监听地址（默认 `0.0.0.0`）
- `LAN_PORT`：端口（默认 `8000`）
- `ROOT_DIR`：共享根目录（默认 `./shared`）
- `AUTH_ENABLED`：是否启用登录（默认 `true`）
- `ADMIN_USER` / `ADMIN_PASSWORD`：登录账号密码
- `MAX_TEXT_PREVIEW_KB`：文本预览最大读取量

## 使用说明

- **上传文件**：点击“上传文件”或拖拽到浏览器即可
- **上传文件夹**：点击“上传文件夹”，选择目录即可（Chrome/Edge 支持）
- **下载文件**：右键菜单选择“下载”或点击文件名自动下载
- **下载文件夹**：右键菜单“下载”，自动打包为 zip
- **预览**：图片/视频/文本点击即可弹窗预览
- **复制链接**：一键复制当前目录 URL
- **暗黑模式**：点击“暗黑模式”切换，记忆在本地

## 常见问题

1. **提示无法访问**
   - 确认手机/电脑在同一 Wi-Fi/局域网
   - 防火墙需允许 Python/端口访问

2. **文件夹上传失败**
   - `webkitdirectory` 依赖浏览器能力，建议使用 Chrome/Edge

3. **内网无外网，Tailwind/HTMX 无法加载**
   - 目前使用 CDN，如需离线可下载对应静态文件放到 `static/` 并替换模板中的引用

## 安全建议

- 仅建议在局域网使用，不要暴露公网
- 如需公网访问，请使用 VPN 或其他安全传输方式

---

## 一键启动命令

```
python main.py
```

## 访问示例

```
http://192.168.1.100:8000
```
