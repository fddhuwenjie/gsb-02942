"""
远程关机客户端
支持后台运行，接收服务端的关机/重启/定时关机命令
"""
import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import uuid
from datetime import datetime

import websockets

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RemoteShutdownClient:
    """远程关机客户端"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.client_id = self.get_or_create_client_id()
        self.websocket = None
        self.running = True
        self.scheduled_shutdown = None
        
    def load_config(self, config_path: str) -> dict:
        """加载配置"""
        default_config = {
            "server_url": "ws://localhost:8000/ws/client",
            "token": "client-secret-token-2942",
            "heartbeat_interval": 30,
            "reconnect_interval": 5
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config.update(config)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")
        
        return default_config
    
    def get_or_create_client_id(self) -> str:
        """获取或创建客户端ID"""
        id_file = "client_id.txt"
        
        if os.path.exists(id_file):
            with open(id_file, 'r') as f:
                return f.read().strip()
        
        # 基于MAC地址和主机名生成唯一ID
        mac = uuid.getnode()
        hostname = socket.gethostname()
        client_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{mac}-{hostname}").hex
        
        with open(id_file, 'w') as f:
            f.write(client_id)
        
        return client_id
    
    def get_system_info(self) -> dict:
        """获取系统信息"""
        return {
            "hostname": socket.gethostname(),
            "ip_address": self.get_local_ip(),
            "os_info": f"{platform.system()} {platform.release()}"
        }
    
    def get_local_ip(self) -> str:
        """获取本机IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    async def connect(self):
        """连接到服务器"""
        url = f"{self.config['server_url']}?token={self.config['token']}"
        
        while self.running:
            try:
                logger.info(f"正在连接服务器: {self.config['server_url']}")
                
                async with websockets.connect(url) as websocket:
                    self.websocket = websocket
                    
                    # 发送注册信息
                    register_data = {
                        "type": "register",
                        "client_id": self.client_id,
                        **self.get_system_info()
                    }
                    await websocket.send(json.dumps(register_data))
                    
                    # 等待注册确认
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if data.get("type") == "registered":
                        logger.info("注册成功，已连接到服务器")
                        
                        # 启动心跳任务
                        heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                        
                        # 处理消息
                        try:
                            await self.message_loop()
                        finally:
                            heartbeat_task.cancel()
                    else:
                        logger.error(f"注册失败: {data}")
                        
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"连接断开: {e}")
            except Exception as e:
                logger.error(f"连接错误: {e}")
            
            if self.running:
                logger.info(f"{self.config['reconnect_interval']}秒后重连...")
                await asyncio.sleep(self.config['reconnect_interval'])
    
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running and self.websocket:
            try:
                await asyncio.sleep(self.config['heartbeat_interval'])
                if self.websocket:
                    await self.websocket.send(json.dumps({"type": "heartbeat"}))
                    logger.debug("发送心跳")
            except Exception as e:
                logger.error(f"心跳发送失败: {e}")
                break
    
    async def message_loop(self):
        """消息处理循环"""
        while self.running and self.websocket:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if data.get("type") == "heartbeat_ack":
                    logger.debug("收到心跳确认")
                    
                elif data.get("type") == "command":
                    await self.handle_command(data)
                    
            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as e:
                logger.error(f"消息处理错误: {e}")
    
    async def handle_command(self, data: dict):
        """处理命令"""
        command = data.get("command")
        params = data.get("params", {})
        
        logger.info(f"收到命令: {command}, 参数: {params}")
        
        result = {"type": "command_result", "command": command}
        
        try:
            if command == "shutdown":
                result["result"] = "executing"
                await self.send_result(result)
                self.execute_shutdown()
                
            elif command == "restart":
                result["result"] = "executing"
                await self.send_result(result)
                self.execute_restart()
                
            elif command == "schedule_shutdown":
                minutes = params.get("minutes", 10)
                self.schedule_shutdown_task(minutes)
                result["result"] = f"scheduled_{minutes}min"
                await self.send_result(result)
                
            elif command == "cancel_shutdown":
                self.cancel_scheduled_shutdown()
                result["result"] = "cancelled"
                await self.send_result(result)
                
            else:
                result["result"] = "unknown_command"
                await self.send_result(result)
                
        except Exception as e:
            result["result"] = f"error: {e}"
            await self.send_result(result)
    
    async def send_result(self, result: dict):
        """发送命令执行结果"""
        if self.websocket:
            await self.websocket.send(json.dumps(result))
    
    def execute_shutdown(self):
        """执行关机"""
        logger.info("执行关机命令...")
        system = platform.system()
        
        if system == "Windows":
            subprocess.run(["shutdown", "/s", "/t", "5", "/c", "远程关机命令"], shell=True)
        elif system == "Linux":
            subprocess.run(["shutdown", "-h", "+1", "远程关机命令"], shell=True)
        elif system == "Darwin":  # macOS
            subprocess.run(["sudo", "shutdown", "-h", "+1"], shell=True)
    
    def execute_restart(self):
        """执行重启"""
        logger.info("执行重启命令...")
        system = platform.system()
        
        if system == "Windows":
            subprocess.run(["shutdown", "/r", "/t", "5", "/c", "远程重启命令"], shell=True)
        elif system == "Linux":
            subprocess.run(["shutdown", "-r", "+1", "远程重启命令"], shell=True)
        elif system == "Darwin":  # macOS
            subprocess.run(["sudo", "shutdown", "-r", "+1"], shell=True)
    
    def schedule_shutdown_task(self, minutes: int):
        """设置定时关机"""
        logger.info(f"设置 {minutes} 分钟后关机")
        system = platform.system()
        
        # 取消之前的定时任务
        self.cancel_scheduled_shutdown()
        
        if system == "Windows":
            seconds = minutes * 60
            subprocess.run(["shutdown", "/s", "/t", str(seconds), "/c", f"定时关机：{minutes}分钟后"], shell=True)
        elif system == "Linux":
            subprocess.run(["shutdown", "-h", f"+{minutes}", "定时关机"], shell=True)
        elif system == "Darwin":
            subprocess.run(["sudo", "shutdown", "-h", f"+{minutes}"], shell=True)
        
        self.scheduled_shutdown = datetime.now()
    
    def cancel_scheduled_shutdown(self):
        """取消定时关机"""
        logger.info("取消定时关机")
        system = platform.system()
        
        if system == "Windows":
            subprocess.run(["shutdown", "/a"], shell=True)
        elif system == "Linux":
            subprocess.run(["shutdown", "-c"], shell=True)
        elif system == "Darwin":
            subprocess.run(["sudo", "killall", "shutdown"], shell=True)
        
        self.scheduled_shutdown = None
    
    def stop(self):
        """停止客户端"""
        self.running = False
        logger.info("客户端停止")


async def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("远程关机客户端启动")
    logger.info("=" * 50)
    
    client = RemoteShutdownClient()
    
    try:
        await client.connect()
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        client.stop()


if __name__ == "__main__":
    asyncio.run(main())
