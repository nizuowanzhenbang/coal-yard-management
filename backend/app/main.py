"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models.user import User, UserRole
from app.models.yard import CoalYard
from app.models.stock_in import StockIn
from app.models.stock_out import StockOut
from app.models.inventory_snapshot import InventorySnapshot
from app.models.stocktake import Stocktake
from app.models.temperature import TemperatureReading
from app.api import auth, yards, stock_in, stock_out, stocktake, dashboard, temperature
from app.api.deps import hash_password

_ = (User, CoalYard, StockIn, StockOut, InventorySnapshot, Stocktake, TemperatureReading)


def _create_default_users(db) -> None:
    defaults = [
        ("admin",      "admin123",      UserRole.ADMIN),
        ("operator",   "operator123",   UserRole.OPERATOR),
        ("supervisor", "supervisor123", UserRole.SUPERVISOR),
        ("viewer",     "viewer123",     UserRole.VIEWER),
    ]
    created = []
    for username, pwd, role in defaults:
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(User(
            username=username,
            hashed_password=hash_password(pwd),
            role=role,
            is_active=True,
            created_at=datetime.utcnow(),
        ))
        created.append(username)
    if created:
        db.commit()
        print(f"[启动] 已创建默认账户：{', '.join(created)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _create_default_users(db)
    finally:
        db.close()
    print(f"[启动] {settings.APP_NAME} v{settings.APP_VERSION} 已就绪")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="发电厂煤场库存管理：堆区 + 入场 + 出场 + 盘点 + 库龄预警",
    lifespan=lifespan,
)

allowed = settings.ALLOWED_ORIGINS or [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(yards.router)
app.include_router(stock_in.router)
app.include_router(stock_out.router)
app.include_router(stocktake.router)
app.include_router(dashboard.router)
app.include_router(temperature.router)


@app.get("/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/", tags=["系统"])
def root():
    return {"message": f"欢迎使用 {settings.APP_NAME}", "docs": "/docs"}
