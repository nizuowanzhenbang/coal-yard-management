"""上游系统集成客户端：fuel-procurement / coal-quality-monitor。
失败降级返回 None，不阻塞主流程。
"""
from typing import Optional
import httpx

from app.config import settings


def _headers() -> dict:
    return {"X-Integration-Token": settings.INTEGRATION_SECRET}


def fetch_order_info(order_no: str) -> Optional[dict]:
    """从 fuel-procurement 拉订单到货信息：
    {order_no, supplier_name, coal_type, planned_quantity, delivered_quantity, unit_price, contract_no}
    """
    base = (settings.FUEL_PROCUREMENT_URL or "").rstrip("/")
    if not base:
        return None
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(
                f"{base}/api/integration/order-info",
                params={"order_no": order_no},
                headers=_headers(),
            )
            if resp.status_code != 200:
                return None
            payload = resp.json()
            return payload.get("data") if isinstance(payload, dict) else None
    except Exception:
        return None


def notify_order_received(order_no: str, yard_code: str, quantity: float) -> bool:
    """通知 fuel-procurement：该订单已入煤场。失败不抛错。"""
    base = (settings.FUEL_PROCUREMENT_URL or "").rstrip("/")
    if not base:
        return False
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(
                f"{base}/api/integration/yard-stocked",
                json={"order_no": order_no, "yard_code": yard_code, "quantity": quantity},
                headers=_headers(),
            )
            return resp.status_code in (200, 201, 204)
    except Exception:
        return False


def fetch_order_quality(order_no: str) -> Optional[dict]:
    """从 coal-quality-monitor 拉订单化验数据汇总：
    {calorific_value, ash, sulfur, moisture, conclusion}
    """
    base = (settings.QUALITY_SYSTEM_URL or "").rstrip("/")
    if not base:
        return None
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(
                f"{base}/api/integration/order-quality-summary",
                params={"order_no": order_no},
                headers=_headers(),
            )
            if resp.status_code != 200:
                return None
            payload = resp.json()
            return payload.get("data") if isinstance(payload, dict) else None
    except Exception:
        return None
