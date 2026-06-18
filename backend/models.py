"""
数据模型
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """管理员用户"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(128))
    created_at = Column(DateTime, default=datetime.now)


class ClientGroup(Base):
    """客户端分组"""
    __tablename__ = "client_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    description = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.now)
    
    clients = relationship("Client", back_populates="group")


class Client(Base):
    """客户端"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(64), unique=True, index=True)
    hostname = Column(String(100))
    ip_address = Column(String(50))
    os_info = Column(String(100))
    group_id = Column(Integer, ForeignKey("client_groups.id"), nullable=True)
    is_online = Column(Boolean, default=False)
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    group = relationship("ClientGroup", back_populates="clients")


class OperationLog(Base):
    """操作日志"""
    __tablename__ = "operation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(50))
    action = Column(String(50))
    target_client = Column(String(64), nullable=True)
    detail = Column(Text, default="")
    result = Column(String(20), default="success")
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 创建默认管理员
        from auth import get_password_hash
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123")
            )
            db.add(admin)
        
        # 创建默认分组
        default_group = db.query(ClientGroup).filter(ClientGroup.name == "默认分组").first()
        if not default_group:
            default_group = ClientGroup(name="默认分组", description="默认客户端分组")
            db.add(default_group)
        
        db.commit()
    finally:
        db.close()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
