# 远程关机管理系统

一个基于 Web 的远程设备关机/重启管理系统，支持批量操作、定时任务和实时监控。

## 功能特性

- 🖥️ 实时监控客户端在线状态
- ⚡ 远程关机/重启/定时关机
- 📦 批量操作多个客户端
- 📁 客户端分组管理
- 📋 操作日志记录
- 🔐 管理员认证

## 项目结构

```
├── backend/          # 服务端
│   ├── main.py       # 主程序
│   ├── models.py     # 数据模型
│   ├── auth.py       # 认证模块
│   ├── websocket_manager.py  # WebSocket管理
│   └── templates/    # HTML模板
├── client/           # 客户端
│   ├── client.py     # 客户端程序
│   ├── config.json   # 配置文件
│   ├── build.py      # 打包脚本
│   └── build.bat     # Windows打包批处理
└── docker-compose.yml
```

## 快速开始

### 1. 启动服务端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

服务端将在 http://localhost:8000 启动

默认管理员账号：`admin` / `admin123`

### 2. 运行客户端

```bash
cd client
pip install -r requirements.txt
python client.py
```

### 3. 打包客户端为 EXE

Windows:
```bash
cd client
build.bat
```

或使用 Python:
```bash
cd client
python build.py
```

打包后的文件在 `client/dist/` 目录

## 配置说明

### 客户端配置 (client/config.json)

```json
{
    "server_url": "ws://服务器IP:8000/ws/client",
    "token": "client-secret-token-2942",
    "heartbeat_interval": 30,
    "reconnect_interval": 5
}
```

### 环境变量

- `SECRET_KEY`: JWT密钥
- `CLIENT_TOKEN`: 客户端认证Token
- `DATABASE_URL`: 数据库连接URL

## 部署

### Docker 部署

```bash
docker-compose up -d
```

### 手动部署

1. 安装 Python 3.8+
2. 安装依赖: `pip install -r requirements.txt`
3. 运行服务端: `python backend/main.py`
4. 在客户端机器运行客户端程序

## 安全说明

- 请修改默认的管理员密码
- 请修改 `CLIENT_TOKEN` 为自定义值
- 建议使用 HTTPS/WSS 进行通信
- 客户端需要管理员权限才能执行关机操作

## License

MIT
