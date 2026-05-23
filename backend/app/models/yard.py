"""煤场堆区模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base


class YardStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"           # 正常使用
    MAINTENANCE = "MAINTENANCE" # 检修中
    DISABLED = "DISABLED"       # 停用


class CoalYard(Base):
    """煤场堆区。每个堆区只放一种煤种（混煤场景另开记录）。"""
    __tablename__ = "coal_yards"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False, comment="堆区编号")
    name = Column(String(100), nullable=False, comment="堆区名称")
    designated_coal_type = Column(String(50), nullable=False, comment="设计煤种")
    capacity = Column(Float, nullable=False, comment="设计容量（吨）")

    # 位置
    location = Column(String(200), nullable=True, comment="位置描述")
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)

    status = Column(Enum(YardStatus), default=YardStatus.ACTIVE, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock_ins = relationship("StockIn", back_populates="yard", cascade="all, delete-orphan")
    stock_outs = relationship("StockOut", back_populates="yard", cascade="all, delete-orphan")
    stocktakes = relationship("Stocktake", back_populates="yard", cascade="all, delete-orphan")
