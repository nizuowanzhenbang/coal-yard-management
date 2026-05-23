"""应用配置"""
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./coal_yard.db"
    SECRET_KEY: str = "coal-yard-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    APP_NAME: str = "发电厂煤场库存管理系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ALLOWED_ORIGINS: Optional[List[str]] = None

    # 集成：燃料采购系统（按订单号反查到货量、回传"已入库"通知）
    FUEL_PROCUREMENT_URL: str = ""
    # 集成：煤质化验系统（按订单号查化验结果）
    QUALITY_SYSTEM_URL: str = ""
    # 共享密钥（与上游 fuel-procurement / coal-quality-monitor 约定一致）
    INTEGRATION_SECRET: str = "coal-integration-shared-secret"

    # 库龄预警阈值（天）
    AGING_WARN_DAYS: int = 15
    AGING_DANGER_DAYS: int = 30

    # 温度告警阈值（℃）
    TEMP_WARN: float = 50.0    # 预警
    TEMP_ALERT: float = 65.0   # 告警
    TEMP_DANGER: float = 80.0  # 危险（接近自燃点）

    # 大额出场审批阈值（吨）
    LARGE_STOCKOUT_THRESHOLD: float = 5000.0

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
