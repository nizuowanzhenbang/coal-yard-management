"""每日库存快照（用于趋势分析）"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.database import Base


class InventorySnapshot(Base):
    """每日 0 点（或手工触发）生成各堆区的库存快照"""
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(DateTime, nullable=False, index=True, comment="快照日期")
    yard_id = Column(Integer, ForeignKey("coal_yards.id"), nullable=False, index=True)
    yard_code = Column(String(50), nullable=False)
    coal_type = Column(String(50), nullable=False)

    inventory = Column(Float, nullable=False, comment="库存量（吨）")
    capacity = Column(Float, nullable=False, comment="设计容量（吨）")
    utilization = Column(Float, nullable=False, comment="利用率 %")

    in_24h = Column(Float, default=0.0, comment="24h 入场量")
    out_24h = Column(Float, default=0.0, comment="24h 出场量")
    oldest_in_days = Column(Integer, nullable=True, comment="最老批次库龄（天）")

    created_at = Column(DateTime, default=datetime.utcnow)
