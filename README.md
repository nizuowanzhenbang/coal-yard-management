# 煤堆里的"守夜人" · 发电厂煤场库存管理系统

> 🔥 煤场是电厂最被低估的"高风险资产"——煤堆躺得久了会自燃（露天煤堆 30 天就能"烧"起来）、热值会下降（同样多的煤烧出来电更少）、湿度灰分会变。但现实是：煤是堆出来的、靠人估的、谁先进谁后出经常乱套；账面 5 万吨实际盘出来差 2000 吨没人能解释。

**这套系统把煤场从"目测估堆"升级成"逐笔记账"**：每一车煤入场都按订单号 + 化验数据落批次；出场严格走 **FIFO**（先进先出），避免老煤压在底下烂掉；库龄 15 天黄牌、30 天红牌；煤堆温度三档监控（50/65/80℃）防自燃；大额出场（默认 ≥ 5000 吨）必须主管审批。月底盘点账实有差？按比例缩放调差，不破坏 FIFO 顺序。

> ⚠️ **免责声明**：本系统是 **厂内实物管理工具**，不能替代 ERP 财务存货账，也不能替代 DCS 实时出煤量数据。

---

## ⚡ 30 秒看明白你能用它做什么

| 你是谁 | 它帮你做什么 |
|---|---|
| 👷 煤场操作员 | 入场登记（自动拉订单/化验数据）、出场登记（自动 FIFO 扣减） |
| 🛡️ 煤场主管 | 大额出场审批、盘点审批、堆区检修/停用 |
| 🔥 安全员 | 看 24h 高温测点、煤堆温度趋势、库龄超 30 天的红色批次 |
| 🏭 燃料部主任 | 看库存总量 / 各堆区库龄分布 / 配煤建议榜 |
| 📊 化验室 | 入场化验数据自动同步给堆区，每笔煤都能追溯到化验单 |

---

## ✨ 核心场景

### 📐 多堆区 + 一区一煤种
- 堆区编号 `DQ-NNN`，每个堆区**只放一种煤种**（动力煤 / 长焰煤 / 弱粘煤 / 褐煤……），入场煤种不匹配直接拒
- 容量硬约束：入场量超过 `堆区容量 - 当前库存` 直接阻断
- 状态机：`ACTIVE ⇄ MAINTENANCE → DISABLED`（停用前必须清空库存）

### 📦 入场：自动拉订单 + 化验数据
关联 `order_no` 时自动调用两个兄弟系统：
> 🔗 **集成链路**
> - `GET ${FUEL_PROCUREMENT_URL}/api/integration/order-info?order_no=...` → 拉供应商 / 合同号 / 计划量
> - `GET ${QUALITY_SYSTEM_URL}/api/integration/order-quality-summary?order_no=...` → 拉热值 / 灰分 / 硫分 / 水分
> - 入场成功后回调 `POST ${FUEL_PROCUREMENT_URL}/api/integration/yard-stocked` 通知采购系统"已入煤场"
> - 共享 `INTEGRATION_SECRET`（HTTP header `X-Integration-Token`），未配置 URL 时降级人工录入

### 🚛 出场：严格 FIFO，避免老煤烂底
按 `stocked_at` 升序扣减堆区里 `remaining_quantity > 0` 的批次，扣减明细 JSON 写入 `fifo_breakdown` 字段，每一吨煤都能追溯到具体入场批次。

### 🌡️ 自燃温度三档监控
| 阈值 | 含义 |
|---|---|
| ≥ 50℃ | `WARN` 关注（蓝） |
| ≥ 65℃ | `ALERT` 警告（黄） |
| ≥ 80℃ | `DANGER` 危险（红） |

支持单堆区 7 天温度趋势 + 24h 全场最高测点榜，Dashboard 直接 KPI"24h 高温测点数"。

### 🏆 入煤综合评分 + 配煤建议
> 💡 **评分公式**：
> `base = 热值分(60–95) - 灰分扣(≤10) - 硫分扣(≤8) - 水分扣(≤5)`
> `aging_decay：≤15 天不扣 / 15–30 线性 0–5 / 30–60 线性 5–20 / >60 封顶 -20`
>
> Dashboard 按 (评分 + 库龄权重) 排序给出"配煤优先"榜——告诉值长该烧哪堆煤效益最高。

### 🛂 大额出场审批 + 盘点调差
- 大额出场（默认 ≥ 5000 吨）走 `PENDING_APPROVAL → APPROVED/REJECTED`，主管二次校验库存才执行 FIFO 扣减
- 盘点：实测 vs 账面，通过则按 `actual / book` 比例缩放该堆区**所有有剩余的批次**，不破坏 FIFO 顺序

---

## 🚀 快速开始

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed_data.py                  # 演示数据：5 堆区 + 20 入场 + 15 出场 + 1 待审盘点
uvicorn app.main:app --reload --port 8001

# 前端
cd frontend
npm install
npm run dev                          # http://localhost:5174
```

打开 http://localhost:5174 → 用 `admin / admin123` 登录。

## 🔐 默认账户

| 用户名 | 密码 | 角色 | 主要权限 |
|---|---|---|---|
| `admin` | `admin123` | 管理员 | 全部 |
| `operator` | `operator123` | 操作员 | 堆区登记 / 入场 / 出场 / 盘点录入 |
| `supervisor` | `supervisor123` | 主管 | 大额出场审批 / 盘点审批 / 堆区停用 |
| `viewer` | `viewer123` | 只读 | 仅查看 |

> 🔒 生产部署请务必删掉 seed 用户、改强密码。

---

## 📋 业务规则速查

| 项 | 规则 |
|---|---|
| 堆区入场 | 必须 `ACTIVE` + 煤种一致 + 量 ≤ 剩余容量 |
| 堆区停用 | 库存必须为 0 |
| 库龄黄牌 / 红牌 | 15 天 / 30 天（env `AGING_WARN_DAYS / AGING_DANGER_DAYS` 可调） |
| 温度阈值 | 50 / 65 / 80 ℃（env 可调） |
| 大额出场阈值 | 5000 吨（env `LARGE_STOCKOUT_THRESHOLD` 可调） |
| 编号规则 | 堆区 `DQ-NNN` / 入场 `IN-YYYYMMDD-NNNN` / 出场 `OUT-YYYYMMDD-NNNN` / 盘点 `PD-YYYYMMDD-NNN` |

---

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI · SQLAlchemy · Pydantic v2 · JWT |
| 前端 | React 18 · TypeScript · Ant Design 5 · ECharts · Zustand · Vite |
| 数据 | SQLite（开发）/ PostgreSQL（生产） |
| 端口 | 后端 `8001` / 前端 `5174` |

## 📁 目录结构

```
coal-yard-management/
├── backend/
│   ├── app/
│   │   ├── api/         # auth / yards / stock_in / stock_out / stocktake / temperature / dashboard
│   │   ├── models/      # User / CoalYard / StockIn / StockOut / Stocktake / TemperatureReading / InventorySnapshot
│   │   ├── schemas/
│   │   ├── utils/       # helpers / csv_export / integration_client / coal_score
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── seed_data.py
└── frontend/
    └── src/
        ├── pages/       # Dashboard / YardList / StockInList / StockOutList / StocktakeList / Temperature / LoginPage
        ├── components/  # Layout
        ├── api/
        ├── stores/
        └── types/
```

---

## 🔗 智慧发电厂全家桶中的位置

本项目是 [smart-power-plant](https://github.com/nizuowanzhenbang/smart-power-plant) 七大子系统中的"煤场库存"模块，是采购到燃用之间的实物管理层：

```
coal-transport-monitor（运到厂门口）
        ↓
fuel-procurement（订单到货登记）
        ↓
*** coal-yard-management（本系统）***
        ↓
锅炉燃用
```

已对接：
| 系统 | 关系 |
|---|---|
| [fuel-procurement](https://github.com/nizuowanzhenbang/fuel-procurement) | 入场拉订单 + 回调"已入煤场" |
| [coal-quality-monitor](https://github.com/nizuowanzhenbang/coal-quality-monitor) | 入场拉化验数据 |

---

## 🚧 路线图

- ✅ **v1.0**：堆区 + 入场 + FIFO 出场 + 盘点 + 库龄预警 + 集成 + 角色权限 + CSV 导出
- ✅ **v2.0**：自燃温度监控 + 入煤综合评分配煤建议 + 大额出场审批
- 🚧 **v3.0**：堆形三维可视化（Three.js）+ 移动端现场扫码 + WebSocket 实时温度告警 + 与 DCS 出煤量自动对账

## 📜 License

私有项目，未开源。
