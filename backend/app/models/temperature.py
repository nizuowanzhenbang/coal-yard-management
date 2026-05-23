"""堆区温度测量记录（自燃监控）"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Enum, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class TemperatureSource(str, enum.Enum):
    MANUAL = "MANUAL"           # 人工红外测温
    SENSOR = "SENSOR"           # 在线温度传感器
    THERMAL_IMAGE = "THERMAL_IMAGE"  # 热成像无人机


class TemperatureReading(Base):
    __tablename__ = "temperature_readings"

    id = Column(Integer, primary_key=True, index=True)
    yard_id = Column(Integer, ForeignKey("coal_yards.id"), nullable=False, index=True)

    spot = Column(String(100), nullable=False, comment="测点位置：东南角/中部/...")
    temperature = Column(Float, nullable=False, comment="温度（℃）")
    source = Column(Enum(TemperatureSource), default=TemperatureSource.MANUAL, nullable=False)
    measured_at = Column(DateTime, nullable=False, index=True, comment="测量时间")
    operator = Column(String(50), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    yard = relationship("CoalYard")
