# 任务跟踪

## v1.0（已完成）

### 后端
- [x] 5 个核心模型（User / CoalYard / StockIn / StockOut / InventorySnapshot / Stocktake）
- [x] 角色权限（ADMIN / OPERATOR / SUPERVISOR / VIEWER）
- [x] 堆区状态机（ACTIVE / MAINTENANCE / DISABLED）+ 容量校验 + 煤种校验
- [x] 入场登记 + 自动同步上游煤质数据 + 通知 fuel-procurement
- [x] 出场登记 FIFO 扣减，明细 JSON 写入 `fifo_breakdown`
- [x] 盘点单：账面/实测/差异计算 + 主管审批 + 按比例缩放调账
- [x] Dashboard：总览 / 堆区利用率 / 煤种占比 / 进出趋势 / 库龄预警 / 库存历史
- [x] 库存快照接口 `POST /dashboard/snapshot`
- [x] CSV 导出（堆区 / 入场 / 出场）
- [x] 集成客户端：fuel-procurement + coal-quality-monitor，失败降级
- [x] seed_data：4 角色账户 + 5 堆区 + 20 入场 + 15 出场 + 当日快照

### 前端
- [x] 登录页 + Layout + 5 个页面 + 角色按钮禁用

## v2.0（已完成）

### 安全：自燃温度监控
- [x] `TemperatureReading` 模型 + `MANUAL/SENSOR/THERMAL_IMAGE` 三种来源
- [x] 三档阈值（默认 50/65/80℃，可通过 env 调整）
- [x] API：录入/列表/删除 + `/hotspots` 24h 高温榜 + `/yard/{id}/trend` 7 天趋势
- [x] Dashboard KPI 加"24h 高温测点（≥65℃）"
- [x] 新增"温度监控"页：高温榜 + 趋势图（堆区下拉）+ 阈值说明卡 + 录入/删除
- [x] seed_data：每堆区 3 测点 × 5 天 + 1 个 72℃ 演示告警点

### 数据：入煤综合评分 + 配煤建议
- [x] `utils/coal_score.py`：热值基础分 - 灰/硫/水扣分 - 库龄衰减
- [x] 入场详情接口 `GET /stock-in/{id}` 附 `score` + 7 项 breakdown
- [x] Dashboard 新增 `/dashboard/blending-advice`：按 (评分 + 库龄权重) 排序
- [x] 前端入场详情展开评分细分卡（基础/扣分/衰减）
- [x] Dashboard 新增"配煤建议"表（TOP3 金/银/铜 + 优先级）

### 业务：大额出场多级审批
- [x] `StockOut` 加 `requires_approval / status / approver / approved_at / approval_notes` 字段
- [x] `StockOutStatus`: PENDING_APPROVAL / APPROVED / REJECTED / COMPLETED
- [x] 创建逻辑：`quantity >= LARGE_STOCKOUT_THRESHOLD`（默认 5000 吨）→ 不立即扣减
- [x] 新增 `POST /stock-out/{id}/approve`（主管），通过则执行 FIFO 扣减，含审批时点库存复核
- [x] 前端：创建表单 quantity ≥5000 自动提示；列表加"大额"标识 + 状态列 + 状态筛选；详情含审批信息 + 审批弹窗
- [x] seed_data：自动为剩余库存最大的堆区生成 1 条 PENDING_APPROVAL 大额单

### 文档
- [x] README.md / CLAUDE.md / TASK.md
- [x] 内存索引同步到 v2.0

## v2.1（已完成，2026-05-20）

### 上游接口端到端联通
- [x] fuel-procurement 配套实现 `GET /api/integration/order-info` 与 `POST /api/integration/yard-stocked`
- [x] coal-quality-monitor 新增 `GET /api/integration/order-quality-summary`，CoalBatch 模型增加 `order_no` 字段
- [x] 三方统一鉴权：`X-Integration-Token` + 共享 `INTEGRATION_SECRET`（兼容煤质系统老的 `X-Integration-Secret`）
- [x] 新增 `backend/integration_smoke_test.py` 三方冒烟测试脚本（默认 8000/8001/8002 端口）

## v3.0（规划）

- [ ] 堆形三维可视化（Three.js）
- [ ] 移动端：现场扫码登记入场
- [ ] 盘点单上传激光扫描原始文件附件
- [ ] 与 DCS 出煤量数据自动对账
- [ ] WebSocket 实时温度告警推送
- [ ] 温度告警短信/邮件通知主管
- [ ] 综合评分接入到出场建议（默认按优先级排序磨煤机用煤）

## 已知简化（v2 仍存在）

- 没有 WebSocket（前端 60s 轮询）
- 库存快照需手动触发或外挂 cron
- 盘点调差按比例缩放，未区分具体损耗批次
- 综合评分公式为线性估算，未对接电厂实际入炉煤质模型
