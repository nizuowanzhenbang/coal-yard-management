"""三系统集成端到端冒烟测试。

需先分别启动 3 个后端：
  - fuel-procurement     : http://127.0.0.1:8000   (uvicorn app.main:app --port 8000)
  - coal-quality-monitor : http://127.0.0.1:8002   (uvicorn app.main:app --port 8002)
  - coal-yard-management : http://127.0.0.1:8001   (uvicorn app.main:app --port 8001)

并设置好对端 URL（coal-yard-management/.env 中 FUEL_PROCUREMENT_URL / QUALITY_SYSTEM_URL 指向上面地址）。

脚本只验证 v2.1 闭环新增接口本身，不创建上下文数据；上下文数据需先用
对应后端的 seed_data.py 或 UI 手工准备好（合同+订单+批次+化验）。

用法：
    python integration_smoke_test.py --order-no PO-20260519-0001 --yard-code DQ-001 --quantity 100
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import httpx

DEFAULT_TOKEN = "coal-integration-shared-secret"
DEFAULT_FUEL_URL = "http://127.0.0.1:8000"
DEFAULT_QUALITY_URL = "http://127.0.0.1:8002"
DEFAULT_YARD_URL = "http://127.0.0.1:8001"


def ok(name: str) -> None:
    print(f"  ✓ {name}")


def fail(name: str, detail: str) -> None:
    print(f"  ✗ {name}")
    print(f"    {detail}")


def show(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def test_fuel_order_info(base: str, token: str, order_no: str) -> bool:
    print(f"[1/4] GET {base}/api/integration/order-info?order_no={order_no}")
    try:
        r = httpx.get(
            f"{base}/api/integration/order-info",
            params={"order_no": order_no},
            headers={"X-Integration-Token": token},
            timeout=5.0,
        )
    except Exception as e:
        fail("请求失败", str(e))
        return False
    if r.status_code == 404:
        fail("订单不存在", "请先在 fuel-procurement 创建该订单")
        return False
    if r.status_code != 200:
        fail(f"HTTP {r.status_code}", r.text)
        return False
    body = r.json()
    data = body.get("data") or {}
    ok("响应成功")
    print(f"    supplier_name = {data.get('supplier_name')}")
    print(f"    coal_type     = {data.get('coal_type')}")
    print(f"    planned/delivered = {data.get('planned_quantity')}/{data.get('delivered_quantity')}")
    return True


def test_fuel_yard_stocked(base: str, token: str, order_no: str, yard_code: str, qty: float) -> bool:
    print(f"\n[2/4] POST {base}/api/integration/yard-stocked")
    try:
        r = httpx.post(
            f"{base}/api/integration/yard-stocked",
            json={"order_no": order_no, "yard_code": yard_code, "quantity": qty},
            headers={"X-Integration-Token": token},
            timeout=5.0,
        )
    except Exception as e:
        fail("请求失败", str(e))
        return False
    if r.status_code != 200:
        fail(f"HTTP {r.status_code}", r.text)
        return False
    body = r.json()
    data = body.get("data") or {}
    ok("入煤场通知已记入订单")
    print(f"    新状态 = {data.get('status')}")
    print(f"    delivered/planned = {data.get('delivered_quantity')}/{data.get('planned_quantity')}")
    return True


def test_quality_summary(base: str, token: str, order_no: str) -> bool:
    print(f"\n[3/4] GET {base}/api/integration/order-quality-summary?order_no={order_no}")
    try:
        r = httpx.get(
            f"{base}/api/integration/order-quality-summary",
            params={"order_no": order_no},
            headers={"X-Integration-Token": token},
            timeout=5.0,
        )
    except Exception as e:
        fail("请求失败", str(e))
        return False
    if r.status_code != 200:
        fail(f"HTTP {r.status_code}", r.text)
        return False
    body = r.json()
    data = body.get("data")
    if data is None:
        ok("接口已就绪，但当前订单尚无关联批次（正常）")
        print("    => 先在 coal-quality-monitor 创建批次时填 order_no 即可联通")
        return True
    ok("响应成功")
    print(f"    batch_count = {data.get('batch_count')}")
    print(f"    conclusion  = {data.get('conclusion')}")
    print(f"    calorific   = {data.get('calorific_value')}")
    print(f"    ash/sulfur/moisture = {data.get('ash')}/{data.get('sulfur')}/{data.get('moisture')}")
    return True


def test_yard_create_stockin(
    yard_base: str, username: str, password: str,
    yard_id: int, coal_type: str, order_no: str, qty: float,
) -> bool:
    """走真实煤场入场流程，验证三方串联（可选）"""
    print(f"\n[4/4] POST {yard_base}/api/stock-in （走真实入场流程）")
    try:
        login = httpx.post(
            f"{yard_base}/api/auth/login",
            data={"username": username, "password": password},
            timeout=5.0,
        )
        if login.status_code != 200:
            fail("登录失败", login.text)
            return False
        token = login.json().get("data", {}).get("access_token") or login.json().get("access_token")
        if not token:
            fail("无法解析 access_token", login.text)
            return False

        from datetime import datetime
        payload = {
            "yard_id": yard_id,
            "order_no": order_no,
            "coal_type": coal_type,
            "quantity": qty,
            "stocked_at": datetime.utcnow().isoformat(),
        }
        r = httpx.post(
            f"{yard_base}/api/stock-in",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        if r.status_code != 200:
            fail(f"HTTP {r.status_code}", r.text)
            return False
        body = r.json()
        data = body.get("data") or {}
        ok("入场登记成功，触发上游集成调用")
        print(f"    入场单号 = {data.get('stockin_no')}")
        print(f"    quality_synced = {data.get('quality_synced')}")
        print(f"    supplier_name  = {data.get('supplier_name')}")
        return True
    except Exception as e:
        fail("请求失败", str(e))
        return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--order-no", required=True, help="已在 fuel-procurement 创建的订单号")
    p.add_argument("--yard-code", default="DQ-001", help="煤场堆区编码，用于通知")
    p.add_argument("--quantity", type=float, default=100.0, help="入场量（吨）")
    p.add_argument("--token", default=DEFAULT_TOKEN)
    p.add_argument("--fuel-url", default=DEFAULT_FUEL_URL)
    p.add_argument("--quality-url", default=DEFAULT_QUALITY_URL)
    p.add_argument("--yard-url", default=DEFAULT_YARD_URL)
    p.add_argument("--run-yard", action="store_true", help="执行第 4 步真实入场流程")
    p.add_argument("--yard-id", type=int, default=1)
    p.add_argument("--coal-type", default="动力煤")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default="admin123")
    args = p.parse_args()

    print("=" * 60)
    print("发电厂燃料链路 - 集成冒烟测试")
    print(f"  订单号: {args.order_no}")
    print(f"  堆区:   {args.yard_code}    数量: {args.quantity} 吨")
    print("=" * 60)

    results = {
        "fuel.order-info": test_fuel_order_info(args.fuel_url, args.token, args.order_no),
        "fuel.yard-stocked": test_fuel_yard_stocked(args.fuel_url, args.token, args.order_no, args.yard_code, args.quantity),
        "quality.order-summary": test_quality_summary(args.quality_url, args.token, args.order_no),
    }
    if args.run_yard:
        results["yard.stockin"] = test_yard_create_stockin(
            args.yard_url, args.username, args.password,
            args.yard_id, args.coal_type, args.order_no, args.quantity,
        )

    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"结果：{passed}/{total} 通过")
    for k, v in results.items():
        flag = "PASS" if v else "FAIL"
        print(f"  [{flag}] {k}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
