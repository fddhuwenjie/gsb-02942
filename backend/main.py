"""
远程关机管理系统 - 服务端主程序
"""
import os
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn

from models import init_db, get_db, User, Client, ClientGroup, OperationLog
from auth import verify_password, create_access_token, verify_token, verify_client_token
from websocket_manager import manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库
    os.makedirs("data", exist_ok=True)
    init_db()
    logger.info("服务端启动成功")
    yield
    logger.info("服务端关闭")


app = FastAPI(title="远程关机管理系统", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ==================== 辅助函数 ====================

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """获取当前登录用户"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    return user


def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    """要求登录"""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


def add_log(db: Session, operator: str, action: str, target: str = None, detail: str = "", result: str = "success"):
    """添加操作日志"""
    log = OperationLog(
        operator=operator,
        action=action,
        target_client=target,
        detail=detail,
        result=result
    )
    db.add(log)
    db.commit()


# ==================== 页面路由 ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """首页 - 重定向到登录或仪表盘"""
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """登录处理"""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "用户名或密码错误"
        })
    
    token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(key="access_token", value=token, httponly=True)
    
    add_log(db, user.username, "登录", detail="管理员登录系统")
    return response


@app.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    """登出"""
    user = get_current_user(request, db)
    if user:
        add_log(db, user.username, "登出", detail="管理员登出系统")
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """仪表盘页面"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    groups = db.query(ClientGroup).all()
    clients = db.query(Client).all()
    online_clients = manager.get_online_clients()
    online_ids = [c["client_id"] for c in online_clients]
    
    # 更新客户端在线状态
    for client in clients:
        client.is_online = client.client_id in online_ids
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "groups": groups,
        "clients": clients,
        "online_clients": online_clients,
        "online_count": len(online_clients)
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: Session = Depends(get_db)):
    """日志页面"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    logs = db.query(OperationLog).order_by(OperationLog.created_at.desc()).limit(100).all()
    
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "user": user,
        "logs": logs
    })


# ==================== API 路由 ====================

@app.get("/api/clients")
async def get_clients(request: Request, db: Session = Depends(get_db)):
    """获取客户端列表"""
    user = require_login(request, db)
    online_clients = manager.get_online_clients()
    return {"clients": online_clients}


@app.post("/api/clients/{client_id}/shutdown")
async def shutdown_client(client_id: str, request: Request, db: Session = Depends(get_db)):
    """关机"""
    user = require_login(request, db)
    
    if not manager.is_online(client_id):
        raise HTTPException(status_code=404, detail="客户端不在线")
    
    success = await manager.send_command(client_id, "shutdown")
    add_log(db, user.username, "关机", client_id, f"向客户端 {client_id} 发送关机命令", "success" if success else "failed")
    
    return {"success": success, "message": "关机命令已发送" if success else "发送失败"}


@app.post("/api/clients/{client_id}/restart")
async def restart_client(client_id: str, request: Request, db: Session = Depends(get_db)):
    """重启"""
    user = require_login(request, db)
    
    if not manager.is_online(client_id):
        raise HTTPException(status_code=404, detail="客户端不在线")
    
    success = await manager.send_command(client_id, "restart")
    add_log(db, user.username, "重启", client_id, f"向客户端 {client_id} 发送重启命令", "success" if success else "failed")
    
    return {"success": success, "message": "重启命令已发送" if success else "发送失败"}


@app.post("/api/clients/{client_id}/schedule")
async def schedule_shutdown(client_id: str, request: Request, minutes: int = 10, db: Session = Depends(get_db)):
    """定时关机"""
    user = require_login(request, db)
    
    if not manager.is_online(client_id):
        raise HTTPException(status_code=404, detail="客户端不在线")
    
    success = await manager.send_command(client_id, "schedule_shutdown", {"minutes": minutes})
    add_log(db, user.username, "定时关机", client_id, f"向客户端 {client_id} 发送 {minutes} 分钟后关机命令", "success" if success else "failed")
    
    return {"success": success, "message": f"{minutes}分钟后关机命令已发送" if success else "发送失败"}


@app.post("/api/clients/{client_id}/cancel")
async def cancel_shutdown(client_id: str, request: Request, db: Session = Depends(get_db)):
    """取消定时关机"""
    user = require_login(request, db)
    
    if not manager.is_online(client_id):
        raise HTTPException(status_code=404, detail="客户端不在线")
    
    success = await manager.send_command(client_id, "cancel_shutdown")
    add_log(db, user.username, "取消关机", client_id, f"向客户端 {client_id} 发送取消关机命令", "success" if success else "failed")
    
    return {"success": success, "message": "取消命令已发送" if success else "发送失败"}


@app.post("/api/batch/shutdown")
async def batch_shutdown(request: Request, db: Session = Depends(get_db)):
    """批量关机"""
    user = require_login(request, db)
    data = await request.json()
    client_ids = data.get("client_ids", [])
    
    results = await manager.broadcast_command(client_ids, "shutdown")
    add_log(db, user.username, "批量关机", None, f"向 {len(client_ids)} 个客户端发送关机命令")
    
    return {"results": results}


@app.post("/api/batch/restart")
async def batch_restart(request: Request, db: Session = Depends(get_db)):
    """批量重启"""
    user = require_login(request, db)
    data = await request.json()
    client_ids = data.get("client_ids", [])
    
    results = await manager.broadcast_command(client_ids, "restart")
    add_log(db, user.username, "批量重启", None, f"向 {len(client_ids)} 个客户端发送重启命令")
    
    return {"results": results}


@app.get("/api/groups")
async def get_groups(request: Request, db: Session = Depends(get_db)):
    """获取分组列表"""
    user = require_login(request, db)
    groups = db.query(ClientGroup).all()
    return {"groups": [{"id": g.id, "name": g.name, "description": g.description} for g in groups]}


@app.post("/api/groups")
async def create_group(request: Request, db: Session = Depends(get_db)):
    """创建分组"""
    user = require_login(request, db)
    data = await request.json()
    
    group = ClientGroup(name=data["name"], description=data.get("description", ""))
    db.add(group)
    db.commit()
    
    add_log(db, user.username, "创建分组", None, f"创建分组: {data['name']}")
    return {"success": True, "id": group.id}


@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, request: Request, db: Session = Depends(get_db)):
    """删除分组"""
    user = require_login(request, db)
    group = db.query(ClientGroup).filter(ClientGroup.id == group_id).first()
    if group:
        add_log(db, user.username, "删除分组", None, f"删除分组: {group.name}")
        db.delete(group)
        db.commit()
    return {"success": True}


@app.get("/api/logs")
async def get_logs(request: Request, limit: int = 50, db: Session = Depends(get_db)):
    """获取操作日志"""
    user = require_login(request, db)
    logs = db.query(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit).all()
    return {"logs": [
        {
            "id": log.id,
            "operator": log.operator,
            "action": log.action,
            "target_client": log.target_client,
            "detail": log.detail,
            "result": log.result,
            "created_at": log.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for log in logs
    ]}


# ==================== WebSocket ====================

@app.websocket("/ws/client")
async def websocket_endpoint(websocket: WebSocket, token: str = "", db: Session = Depends(get_db)):
    """客户端 WebSocket 连接"""
    # 验证客户端Token
    if not verify_client_token(token):
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    # 等待客户端发送注册信息
    try:
        await websocket.accept()
        data = await websocket.receive_json()
        
        if data.get("type") != "register":
            await websocket.close(code=4002, reason="Invalid registration")
            return
        
        client_id = data.get("client_id")
        info = {
            "hostname": data.get("hostname", "unknown"),
            "ip_address": data.get("ip_address", "unknown"),
            "os_info": data.get("os_info", "unknown")
        }
        
        # 保存或更新客户端信息到数据库
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            client = Client(client_id=client_id, **info)
            db.add(client)
        else:
            client.hostname = info["hostname"]
            client.ip_address = info["ip_address"]
            client.os_info = info["os_info"]
        client.is_online = True
        client.last_heartbeat = datetime.now()
        db.commit()
        
        # 添加到连接管理器
        manager.active_connections[client_id] = websocket
        manager.client_info[client_id] = info
        
        logger.info(f"客户端注册成功: {client_id} - {info['hostname']}")
        
        # 发送确认
        await websocket.send_json({"type": "registered", "message": "注册成功"})
        
        # 保持连接，处理消息
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "heartbeat":
                manager.update_heartbeat(client_id)
                client.last_heartbeat = datetime.now()
                db.commit()
                await websocket.send_json({"type": "heartbeat_ack"})
            
            elif data.get("type") == "command_result":
                logger.info(f"客户端 {client_id} 命令执行结果: {data.get('result')}")
    
    except WebSocketDisconnect:
        logger.info(f"客户端断开连接: {client_id if 'client_id' in dir() else 'unknown'}")
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
    finally:
        if 'client_id' in dir() and client_id:
            manager.disconnect(client_id)
            client = db.query(Client).filter(Client.client_id == client_id).first()
            if client:
                client.is_online = False
                db.commit()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
