# 纯局域网 FTP 文件传输（Python + pyftpdlib）

本项目用于局域网内文件/文件夹传输，支持 Windows、macOS、Linux、Android、iOS 设备。仅建议在内网使用，不要暴露公网。

## 依赖安装

```
pip install -r requirements.txt
```

## 运行服务器

```
python main.py
```

启动后会显示：
- 局域网 IP:端口
- 匿名登录提示
- 连接二维码（手机扫码）

## 连接方式（推荐客户端）

### Windows / macOS / Linux
- FileZilla
  1. 打开 FileZilla
  2. 主机：填 `局域网IP`
  3. 端口：`2121`（或你在 config.ini 中设置的端口）
  4. 用户名：`anonymous`（匿名）或自定义用户名
  5. 密码：匿名留空或填写配置的密码
  6. 连接后可上传/下载/删除/重命名/创建文件夹

### Android
- CX 文件浏览器
- FE File Explorer
  1. 新建 FTP 连接
  2. 主机：`局域网IP`
  3. 端口：`2121`
  4. 用户名/密码：按需填写

### iOS
- Documents by Readdle
  1. 打开 Documents
  2. 选择“连接服务器”或“添加 FTP”
  3. 地址：`局域网IP`
  4. 端口：`2121`
  5. 用户名/密码：按需填写

## 如何获取本机局域网 IP

### Windows
```
ipconfig
```
查找“IPv4 地址”。

### macOS
```
ifconfig | grep "inet "
```

### Linux
```
ip a
```

## 手机端连接示例

- 地址：`192.168.1.100`
- 端口：`2121`
- 用户名：`anonymous`
- 密码：留空

## 配置说明

配置文件 `config.ini` 中可修改：
- FTP 根目录 `root_dir`
- 监听端口 `listen_port`
- 局域网 IP `lan_ip`（可设为 `auto` 自动获取）
- 被动端口范围 `pasv_min_port`/`pasv_max_port`
- 匿名登录开关与权限
- 最大连接数、超时时间

用户配置支持两种方式：
1. 在 `config.ini` 的 `[users]` 中直接添加：
   - `用户名 = 密码, 权限, 目录(可选)`
2. 在 `users.ini` 中每个用户一个 section：
   - `password`, `perm`, `home`

## 测试脚本

```
python client_test.py --host 192.168.1.100 --port 2121 --user anonymous --password ""
```

## 安全提示

- 本项目仅用于局域网内部传输
- 不建议暴露公网或在不受信任网络使用
- 如需公网访问，请考虑 VPN 或更安全的传输方案

## Web 可视化管理页面

默认启用，浏览器访问：
```
http://<局域网IP>:8080
```
默认账号密码：
- 用户名：`admin`
- 密码：`admin`

可在 `config.ini` 的 `[web]` 中修改端口、账号密码或关闭。
