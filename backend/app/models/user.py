"""用户模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, Boolean
from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"             # 燃料部主任
    OPERATOR = "OPERATOR"       # 煤场操作员（堆区登记/入场/出场）
    SUPERVISOR = "SUPERVISOR"   # 煤场主管（盘点审批/堆区停用）
    VIEWER = "VIEWER"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    hashed_password = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
