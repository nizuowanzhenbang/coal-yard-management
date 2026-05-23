"""演示数据：4 角色账户 + 5 堆区 + 20 入场 + 15 出场 + 当日快照"""
import json
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.yard import CoalYard, YardStatus
from app.models.stock_in import StockIn
from app.models.stock_out import StockOut, StockOutStatus
from app.models.temperature import TemperatureReading, TemperatureSource
from app.models.inventory_snapshot import InventorySnapshot
from app.models.stocktake import Stocktake, StocktakeStatus
from app.api.deps import hash_password
from app.utils.helpers import (
    generate_yard_code, generate_stockin_no,
    generate_stockout_no, generate_stocktake_no,
)


YARDS = [
    ("一号堆区", "动力煤", 50000, "厂区东南角"),
    ("二号堆区", "动力煤", 60000, "厂区东南角"),
    ("三号堆区", "长焰煤", 30000, "厂区东侧"),
    ("四号堆区", "褐煤",   25000, "厂区南侧"),
    ("五号堆区", "混煤",   40000, "厂区西南角"),
]

SUPPLIERS = [
    ("神华神东煤炭集团", "陕西神木"),
    ("中煤平朔煤业公司", "山西朔州"),
    ("伊泰煤炭股份", "内蒙古鄂尔多斯"),
    ("陕煤化运销集团", "陕西榆林"),
    ("同煤集团", "山西大同"),
    ("准能集团", "内蒙古准格尔"),
]

DESTINATIONS = ["#1机组A磨", "#1机组B磨", "#2机组A磨", "#2机组B磨", "#3机组A磨"]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 角色账户
        defaults = [
            ("admin",      "admin123",      UserRole.ADMIN),
            ("operator",   "operator123",   UserRole.OPERATOR),
            ("supervisor", "supervisor123", UserRole.SUPERVISOR),
            ("viewer",     "viewer123",     UserRole.VIEWER),
        ]
        for username, pwd, role in defaults:
            if not db.query(User).filter(User.username == username).first():
                db.add(User(
                    username=username, hashed_password=hash_password(pwd),
                    role=role, is_active=True,
                ))
        db.commit()
        print("✓ 默认账户已就绪：admin/operator/supervisor/viewer")

        # 堆区
        if db.query(CoalYard).count() == 0:
            for i, (name, coal_type, cap, loc) in enumerate(YARDS, 1):
                db.add(CoalYard(
                    code=generate_yard_code(i),
                    name=name,
                    designated_coal_type=coal_type,
                    capacity=cap,
                    location=loc,
                    longitude=round(110 + random.uniform(0, 0.05), 4),
                    latitude=round(38 + random.uniform(0, 0.05), 4),
                    status=YardStatus.ACTIVE,
                ))
            db.commit()
            print(f"✓ 已生成 {len(YARDS)} 个堆区")

        yards = db.query(CoalYard).all()

        # 入场记录：每个堆区 4 条，时间分布在过去 45 天
        if db.query(StockIn).count() == 0:
            now = datetime.utcnow()
            seq = 1
            for y in yards:
                # 每堆区生成 4 条入场，间隔 7~14 天
                cumulative = 0.0
                for k in range(4):
                    days_ago = 45 - k * 12 - random.randint(0, 3)
                    stocked_at = now - timedelta(days=days_ago)
                    qty = round(random.uniform(3000, 8000), 1)
                    # 不要超容量
                    if cumulative + qty > y.capacity * 0.85:
                        qty = round(y.capacity * 0.85 - cumulative, 1)
                        if qty <= 0:
                            continue
                    cumulative += qty
                    supplier, origin = random.choice(SUPPLIERS)
                    order_no = f"PO-{stocked_at.strftime('%Y%m%d')}-{random.randint(1, 99):04d}"

                    db.add(StockIn(
                        stockin_no=f"IN-{stocked_at.strftime('%Y%m%d')}-{seq:04d}",
                        yard_id=y.id,
                        order_no=order_no,
                        supplier_name=supplier,
                        contract_no=f"HT-{stocked_at.strftime('%Y%m')}-{random.randint(1, 30):04d}",
                        coal_type=y.designated_coal_type,
                        quantity=qty,
                        remaining_quantity=qty,
                        calorific_value=random.randint(4800, 5800),
                        ash=round(random.uniform(15, 25), 1),
                        sulfur=round(random.uniform(0.4, 1.0), 2),
                        moisture=round(random.uniform(8, 15), 1),
                        quality_synced=False,
                        stocked_at=stocked_at,
                        operator="operator",
                        transport_mode=random.choice(["铁路", "汽运"]),
                    ))
                    seq += 1
            db.commit()
            print(f"✓ 已生成 {seq - 1} 条入场记录")

        # 出场记录：从最早入场批次开始 FIFO 扣减
        if db.query(StockOut).count() == 0:
            now = datetime.utcnow()
            seq = 1
            for y in yards:
                # 每堆区 3 条出场
                for k in range(3):
                    days_ago = 30 - k * 10 - random.randint(0, 3)
                    if days_ago < 0:
                        continue
                    delivered_at = now - timedelta(days=days_ago)
                    qty = round(random.uniform(1000, 4000), 1)

                    # FIFO 扣减（仅对 stocked_at <= delivered_at 的批次）
                    batches = (
                        db.query(StockIn)
                        .filter(
                            StockIn.yard_id == y.id,
                            StockIn.remaining_quantity > 0,
                            StockIn.stocked_at <= delivered_at,
                        )
                        .order_by(StockIn.stocked_at.asc())
                        .all()
                    )
                    available = sum(b.remaining_quantity for b in batches)
                    if available < qty:
                        qty = round(available * 0.8, 1)
                    if qty <= 0:
                        continue

                    need = qty
                    breakdown = []
                    for b in batches:
                        if need <= 0.001:
                            break
                        take = min(b.remaining_quantity, need)
                        b.remaining_quantity = round(b.remaining_quantity - take, 3)
                        need -= take
                        breakdown.append({
                            "stockin_no": b.stockin_no,
                            "taken": round(take, 3),
                        })

                    db.add(StockOut(
                        stockout_no=f"OUT-{delivered_at.strftime('%Y%m%d')}-{seq:04d}",
                        yard_id=y.id,
                        coal_type=y.designated_coal_type,
                        quantity=qty,
                        destination=random.choice(DESTINATIONS),
                        purpose="发电",
                        delivered_at=delivered_at,
                        operator="operator",
                        fifo_breakdown=json.dumps(breakdown, ensure_ascii=False),
                        requires_approval=False,
                        status=StockOutStatus.COMPLETED,
                    ))
                    seq += 1
            db.commit()
            print(f"✓ 已生成 {seq - 1} 条出场记录")

        # 当日快照
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if not db.query(InventorySnapshot).filter(InventorySnapshot.snapshot_date == today).first():
            from sqlalchemy import func
            for y in yards:
                inv = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
                    StockIn.yard_id == y.id
                ).scalar() or 0
                oldest = (
                    db.query(StockIn)
                    .filter(StockIn.yard_id == y.id, StockIn.remaining_quantity > 0)
                    .order_by(StockIn.stocked_at.asc())
                    .first()
                )
                oldest_days = (datetime.utcnow() - oldest.stocked_at).days if oldest else None
                db.add(InventorySnapshot(
                    snapshot_date=today,
                    yard_id=y.id,
                    yard_code=y.code,
                    coal_type=y.designated_coal_type,
                    inventory=round(float(inv), 1),
                    capacity=y.capacity,
                    utilization=round(float(inv) / y.capacity * 100, 1) if y.capacity else 0,
                    in_24h=0.0,
                    out_24h=0.0,
                    oldest_in_days=oldest_days,
                ))
            db.commit()
            print("✓ 已生成当日库存快照")

        # 温度演示数据：每堆区 3 个测点 × 近 5 天，一个故意制造高温点
        if db.query(TemperatureReading).count() == 0:
            now = datetime.utcnow()
            spots = ["东南角", "中部", "西北角"]
            for idx, y in enumerate(yards):
                for d in range(5):
                    for spot in spots:
                        base = 30 + random.uniform(-5, 10)
                        # 第一个堆区的中部测点：今天故意拉到 70℃
                        if idx == 0 and spot == "中部" and d == 0:
                            t = 72.0
                        else:
                            t = round(base + random.uniform(-3, 5), 1)
                        db.add(TemperatureReading(
                            yard_id=y.id,
                            spot=spot,
                            temperature=t,
                            source=random.choice([TemperatureSource.MANUAL, TemperatureSource.SENSOR]),
                            measured_at=now - timedelta(days=d, hours=random.randint(0, 23)),
                            operator="operator",
                        ))
            db.commit()
            print("✓ 已生成温度演示数据（含 1 个 72℃ 高温测点）")

        # 大额待审批出场单（演示）
        if yards:
            already_pending = db.query(StockOut).filter(StockOut.status == StockOutStatus.PENDING_APPROVAL).first()
            if not already_pending:
                from sqlalchemy import func as _f
                # 找到剩余库存最大的堆区
                richest = None
                richest_inv = 0
                for y in yards:
                    inv = db.query(_f.coalesce(_f.sum(StockIn.remaining_quantity), 0)).filter(
                        StockIn.yard_id == y.id
                    ).scalar() or 0
                    if float(inv) > richest_inv:
                        richest = y
                        richest_inv = float(inv)
                if richest and richest_inv >= 5000:
                    db.add(StockOut(
                        stockout_no=f"OUT-{datetime.utcnow().strftime('%Y%m%d')}-9001",
                        yard_id=richest.id,
                        coal_type=richest.designated_coal_type,
                        quantity=round(min(richest_inv * 0.4, 8000), 1),
                        destination="#1机组A磨",
                        purpose="发电",
                        delivered_at=datetime.utcnow(),
                        operator="operator",
                        requires_approval=True,
                        status=StockOutStatus.PENDING_APPROVAL,
                        notes="高负荷调度，单次大额上煤申请",
                    ))
                    db.commit()
                    print("✓ 已生成 1 条大额待审批出场单（演示）")

        # 给第一个堆区生成一条待审批盘点单（用于演示）
        if db.query(Stocktake).count() == 0 and yards:
            from sqlalchemy import func
            y0 = yards[0]
            book = db.query(func.coalesce(func.sum(StockIn.remaining_quantity), 0)).filter(
                StockIn.yard_id == y0.id
            ).scalar() or 0
            actual = round(float(book) * 0.97, 1)  # 实测少 3%
            diff = round(actual - float(book), 1)
            db.add(Stocktake(
                stocktake_no=f"PD-{datetime.utcnow().strftime('%Y%m%d')}-001",
                yard_id=y0.id,
                book_inventory=round(float(book), 1),
                actual_inventory=actual,
                diff_quantity=diff,
                diff_rate=round(diff / float(book) * 100, 2) if book else 0,
                measured_at=datetime.utcnow() - timedelta(hours=2),
                measurer="operator",
                method="激光扫描",
                reason="月度盘点；雨季水分蒸发损耗",
                status=StocktakeStatus.PENDING_APPROVAL,
            ))
            db.commit()
            print("✓ 已生成 1 条待审批盘点单（演示）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
