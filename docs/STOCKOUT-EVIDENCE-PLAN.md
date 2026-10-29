# PP058 账面出场依据导出设计与执行计划

用户授权按队列连续实施；沿用FastAPI/SQLAlchemy。只读POST /api/stock-out/{id}/accounting-evidence，登录用户可调用；请求明确声明offset_minutes与time_evidence，配置YARD_SOURCE_INSTANCE区分部署来源。

使用COMPLETED/APPROVED记录；校验0.001吨精度，正有限出场量、非空FIFO、唯一入场引用、正扣减/非负剩余、扣减总和=出场量；关联入场存在且堆区/煤种/stocked_at一致且不晚于出场。引用的当前remaining_quantity不影响历史；盘点可能放大库存，因此不以原始入场量作为历史总上限。原库存并发安全与物理可信度不由此认证。

所有导出文本拒绝NUL/非法Unicode，日期转换UTC须可表示。FIFO JSON重复键拒绝。规范内容SHA256不含导出时刻但包含声明人和时间依据。没有保存新数据库记录，调用者保存响应；不将destination文字映射成unit_code，不建立化验批次对应。

取舍：直接转入炉事实会混淆账面与物理来源；只导出原JSON会传播坏账。选择受校验账面快照，旧数据无法满足约束返回409。

执行采用superpowers:executing-plans：
- [ ] 真实数据库/API测试权限、有限量/精度/合计/引用/状态/时间边界、无写入和摘要稳定性，先失败。
- [ ] services/stockout_evidence.py实现纯导出校验；schemas与api接入、配置来源。
- [ ] SQLite完整测试、PostgreSQL隔离CI、ruff、独立审查。
- [ ] 文档说明、PR合并、默认分支验收、中央回写；进入PP059数量写入保护。
