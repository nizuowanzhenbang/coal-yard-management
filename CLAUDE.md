# Claude Code 项目规则

## 项目定位

发电厂煤场库存管理系统。v1.0 聚焦"堆区 → 入场 → FIFO 出场 → 库龄预警 → 盘点"。是 fuel-procurement（采购）和锅炉燃用之间的实物管理层。

## 技术栈约束

- 后端：FastAPI + SQLAlchemy + Pydantic v2，与 plant-safety / coal-quality-monitor / fuel-procurement 同款分层
- 前端：React 18 + TypeScript + Ant Design 5 + ECharts + Zustand + Vite
- 端口：后端 8001 / 前端 5174（避免与 fuel-procurement 的 8000/5173 冲突）
- 数据库：SQLite（开发）/ PostgreSQL（生产）

## 业务规则

### 堆区状态机
- `ACTIVE` ⇄ `MAINTENANCE` ⇄ `ACTIVE`
- `ACTIVE`/`MAINTENANCE` → `DISABLED`（必须库存为 0）

### 入场登记规则
- 堆区必须 `ACTIVE`，否则拒绝
- 煤种必须 == 堆区设计煤种
- 入场量 ≤ (capacity - current_inventory)
- 关联 `order_no` 时自动尝试拉取 fuel-procurement 订单信息 + coal-quality-monitor 化验数据
- 入场即 `remaining_quantity = quantity`，进入 FIFO 队列

### 出场 FIFO 规则
- 按 `stocked_at ASC` 遍历该堆区 `remaining_quantity > 0` 的批次依次扣减
- 扣减明细 JSON 写入 `fifo_breakdown` 字段
- 不允许从 `DISABLED` 堆区出场

### 库龄阈值
- 默认 `AGING_WARN_DAYS=15`、`AGING_DANGER_DAYS=30`，可通过环境变量调整
- 防自燃 + 防煤质衰减（热值下降、灰分上升）

### 盘点审批
- 提交即 `PENDING_APPROVAL`，账面值即时计算自 `sum(remaining_quantity)`
- 通过 → 按 `actual/book` 比例缩放所有有剩余批次
- 比例缩放不打破 FIFO 顺序，只调数量
- 仅 SUPERVISOR / ADMIN 可审批

### 编号规则
- 堆区：`DQ-NNN`
- 入场：`IN-YYYYMMDD-NNNN`
- 出场：`OUT-YYYYMMDD-NNNN`
- 盘点：`PD-YYYYMMDD-NNN`

## 角色权限

| 角色 | 主要权限 |
|---|---|
| ADMIN | 全部 |
| OPERATOR | 堆区登记/更新、入场、出场、盘点录入、煤质同步 |
| SUPERVISOR | 盘点审批、堆区检修/恢复/停用 |
| VIEWER | 只读 |

后端通过 `deps.require_write` / `deps.require_approver` 拦截；前端通过 `stores/auth.canWrite` / `canApprove` 禁用按钮 + tooltip。

## 集成约定（v1.0 已实现）

- 配置 `FUEL_PROCUREMENT_URL`、`QUALITY_SYSTEM_URL`，未配置时降级
- 共享 `INTEGRATION_SECRET`（HTTP header `X-Integration-Token`）
- 调用对端接口约定：
  - `GET ${FUEL_PROCUREMENT_URL}/api/integration/order-info?order_no=...` → 订单信息
  - `POST ${FUEL_PROCUREMENT_URL}/api/integration/yard-stocked` → 通知已入煤场
  - `GET ${QUALITY_SYSTEM_URL}/api/integration/order-quality-summary?order_no=...` → 化验汇总

## 代码风格

- API 响应统一 `{code, message, data}`，使用 `utils.helpers.api_response`
- 分页用 `paginate_response`
- 中文 docstring 和字段注释
- 前端中文 locale + 中文 label

## v2.0 新增（2026-05-19）

### 自燃温度监控
- `TemperatureReading` 表，三档阈值 `TEMP_WARN/ALERT/DANGER`（50/65/80℃，env 可调）
- API：`/api/temperature` 录入/列表/删除 + `/hotspots`（24h 各测点最高）+ `/yard/{id}/trend`
- Dashboard KPI "24h 高温测点(≥告警)" + 新增"温度监控"菜单页

### 入煤综合评分（`utils/coal_score.py`）
- base = 热值分(60-95) - 灰分扣(≤10) - 硫分扣(≤8) - 水分扣(≤5)
- aging_decay：≤15 天不扣；15-30 线性 0-5；30-60 线性 5-20；>60 封顶 20
- 入场详情接口附 `score + breakdown`，Dashboard `/blending-advice` 按 (评分 + 库龄权重) 排序

### 大额出场多级审批
- `StockOut` 加 `requires_approval/status/approver/approved_at/approval_notes`
- 状态机：PENDING_APPROVAL → APPROVED/REJECTED；小额自动 COMPLETED
- 阈值 `LARGE_STOCKOUT_THRESHOLD`（默认 5000 吨）
- 审批通过才执行 FIFO 扣减，审批时点二次校验库存

## 已知简化

- 没有 WebSocket / 推送（v3 加实时温度告警）
- 盘点调差按比例缩放，不区分具体损耗批次
- 没有移动端（v3 现场扫码）
- 库存快照需手动触发或外挂 cron
- 综合评分公式为线性估算，未对接电厂实际入炉煤质模型
- 与 DCS 对账未实现
