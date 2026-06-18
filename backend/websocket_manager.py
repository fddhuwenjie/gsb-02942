"""
WebSocket 连接管理器
"""
from fastapi import WebSocket
from typing import Dict, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # client_id -> client_info
        self.client_info: Dict[str, dict] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str, info: dict):
        """客户端连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_info[client_id] = {
            **info,
            "connected_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat()
        }
        logger.info(f"客户端连接: {client_id} - {info.get('hostname', 'unknown')}")
    
    def disconnect(self, client_id: str):
        """客户端断开"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_info:
            del self.client_info[client_id]
        logger.info(f"客户端断开: {client_id}")
    
    def update_heartbeat(self, client_id: str):
        """更新心跳时间"""
        if client_id in self.client_info:
            self.client_info[client_id]["last_heartbeat"] = datetime.now().isoformat()
    
    async def send_command(self, client_id: str, command: str, params: dict = None) -> bool:
        """发送命令到客户端"""
        if client_id not in self.active_connections:
            return False
        
        websocket = self.active_connections[client_id]
        message = {
            "type": "command",
            "command": command,
            "params": params or {}
        }
        try:
            await websocket.send_json(message)
            logger.info(f"发送命令到 {client_id}: {command}")
            return True
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            self.disconnect(client_id)
            return False
    
    async def broadcast_command(self, client_ids: list, command: str, params: dict = None) -> dict:
        """批量发送命令"""
        results = {}
        for client_id in client_ids:
            results[client_id] = await self.send_command(client_id, command, params)
        return results
    
    def get_online_clients(self) -> list:
        """获取在线客户端列表"""
        return [
            {"client_id": cid, **info}
            for cid, info in self.client_info.items()
        ]
    
    def is_online(self, client_id: str) -> bool:
        """检查客户端是否在线"""
        return client_id in self.active_connections


manager = ConnectionManager()
