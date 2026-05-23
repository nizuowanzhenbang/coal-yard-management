import { useEffect, useState, useCallback } from 'react'
import { Row, Col, Card, Statistic, Table, Tag, Progress, Empty, Button, message } from 'antd'
import {
  AppstoreOutlined, GoldOutlined, ImportOutlined, ExportOutlined,
  WarningOutlined, AuditOutlined, CameraOutlined, FireOutlined,
  ExperimentOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { ColumnsType } from 'antd/es/table'
import { dashboardApi } from '../api'
import type {
  OverviewData, YardUtilization, CoalTypeInventory,
  InOutTrendItem, AgingAlertItem, InventoryHistoryItem,
  BlendingAdviceItem,
} from '../types'

export default function Dashboard() {
  const [overview, setOverview] = useState<OverviewData | null>(null)
  const [yardUtil, setYardUtil] = useState<YardUtilization[]>([])
  const [coalInv, setCoalInv] = useState<CoalTypeInventory[]>([])
  const [trend, setTrend] = useState<InOutTrendItem[]>([])
  const [aging, setAging] = useState<AgingAlertItem[]>([])
  const [history, setHistory] = useState<InventoryHistoryItem[]>([])
  const [blending, setBlending] = useState<BlendingAdviceItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      const [ov, yu, ci, tr, ag, ih, ba] = await Promise.all([
        dashboardApi.overview(),
        dashboardApi.yardUtilization(),
        dashboardApi.coalTypeInventory(),
        dashboardApi.inOutTrend(30),
        dashboardApi.agingAlert(15),
        dashboardApi.inventoryHistory(30),
        dashboardApi.blendingAdvice(10),
      ])
      setOverview(ov.data); setYardUtil(yu.data); setCoalInv(ci.data)
      setTrend(tr.data); setAging(ag.data); setHistory(ih.data)
      setBlending(ba.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [load])

  const utilOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['库存（吨）', '容量（吨）'], bottom: 0 },
    grid: { left: 60, right: 30, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: yardUtil.map((y) => y.yard_code) },
    yAxis: { type: 'value', name: '吨' },
    series: [
      { name: '库存（吨）', type: 'bar', data: yardUtil.map((y) => y.inventory), itemStyle: { color: '#13a397' } },
      { name: '容量（吨）', type: 'bar', data: yardUtil.map((y) => y.capacity - y.inventory),
        stack: 'cap', itemStyle: { color: '#e8e8e8' } },
    ],
  }

  const coalOption: EChartsOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 吨 ({d}%)' },
    legend: { orient: 'horizontal', bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['50%', '45%'],
      data: coalInv.map((c) => ({ name: c.coal_type, value: c.inventory })),
    }],
  }

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['入场', '出场'], bottom: 0 },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((t) => t.date.slice(5)) },
    yAxis: { type: 'value', name: '吨' },
    series: [
      { name: '入场', type: 'bar', data: trend.map((t) => t.in), itemStyle: { color: '#52c41a' } },
      { name: '出场', type: 'bar', data: trend.map((t) => t.out), itemStyle: { color: '#fa8c16' } },
    ],
  }

  const historyOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: history.map((h) => h.date.slice(5)) },
    yAxis: { type: 'value', name: '吨', scale: true },
    series: [{
      type: 'line', smooth: true, data: history.map((h) => h.inventory),
      itemStyle: { color: '#13a397' }, areaStyle: { color: 'rgba(19,163,151,0.15)' },
    }],
  }

  const agingColumns: ColumnsType<AgingAlertItem> = [
    {
      title: '级别', dataIndex: 'level', width: 70,
      render: (v: string) => v === 'red'
        ? <Tag color="red">红</Tag>
        : v === 'yellow' ? <Tag color="orange">黄</Tag> : <Tag color="green">正常</Tag>,
    },
    { title: '入场单号', dataIndex: 'stockin_no', width: 150 },
    { title: '堆区', dataIndex: 'yard_name', ellipsis: true },
    { title: '煤种', dataIndex: 'coal_type', width: 80 },
    {
      title: '剩余(吨)', dataIndex: 'remaining_quantity', width: 90,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '库龄', dataIndex: 'aging_days', width: 80,
      render: (v: number) => `${v} 天`,
    },
  ]

  const handleSnapshot = async () => {
    try {
      const res = await dashboardApi.takeSnapshot()
      message.success(res.message || '快照已生成')
      load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '生成快照失败')
    }
  }

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="启用堆区"
              value={overview?.active_yards ?? 0}
              prefix={<AppstoreOutlined style={{ color: '#13a397' }} />}
              suffix={<span style={{ fontSize: 13, color: '#999' }}>个</span>}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="总库存（吨）"
              value={overview?.total_inventory ?? 0}
              precision={1}
              prefix={<GoldOutlined style={{ color: '#722ed1' }} />}
              suffix={<span style={{ fontSize: 13, color: '#999' }}>
                / {overview?.total_capacity?.toLocaleString()}（{overview?.utilization}%）
              </span>}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="今日入场（吨）"
              value={overview?.today_in_tons ?? 0}
              precision={1}
              prefix={<ImportOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="今日出场（吨）"
              value={overview?.today_out_tons ?? 0}
              precision={1}
              prefix={<ExportOutlined style={{ color: '#fa8c16' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="库龄红色（吨，>30天）"
              value={overview?.aging_danger_tons ?? 0}
              precision={1}
              prefix={<WarningOutlined style={{ color: '#ff4d4f' }} />}
              valueStyle={{ color: (overview?.aging_danger_tons ?? 0) > 0 ? '#ff4d4f' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="24h 高温测点（≥65℃）"
              value={overview?.hot_spots_24h ?? 0}
              prefix={<FireOutlined style={{ color: '#fa541c' }} />}
              valueStyle={{ color: (overview?.hot_spots_24h ?? 0) > 0 ? '#fa541c' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="待审批盘点单"
              value={overview?.pending_stocktakes ?? 0}
              prefix={<AuditOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading} bodyStyle={{ padding: '16px' }}>
            <Button block icon={<CameraOutlined />} onClick={handleSnapshot}>
              生成当日库存快照
            </Button>
            <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
              生产环境由 cron 每日 0 点触发
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={14}>
          <Card title="各堆区容量利用率" loading={loading}>
            <ReactECharts option={utilOption} style={{ height: 300 }} notMerge />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="煤种库存占比" loading={loading}>
            {coalInv.length === 0 ? <Empty /> : <ReactECharts option={coalOption} style={{ height: 300 }} notMerge />}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
        <Col xs={24} lg={14}>
          <Card title="近30天进出趋势" loading={loading}>
            <ReactECharts option={trendOption} style={{ height: 280 }} notMerge />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="总库存历史（按日快照）" loading={loading}>
            {history.length === 0 ? <Empty description="尚无快照，点击上方按钮生成" />
              : <ReactECharts option={historyOption} style={{ height: 280 }} notMerge />}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            title={<span><WarningOutlined style={{ color: '#fa541c', marginRight: 8 }} />库龄预警榜（FIFO 最老批次）</span>}
            loading={loading}
          >
            {aging.length === 0 ? <Empty description="暂无在库批次" /> : (
              <Table<AgingAlertItem>
                dataSource={aging} columns={agingColumns}
                rowKey="stockin_no" size="small" pagination={false}
                scroll={{ x: 700 }}
                summary={(data) => {
                  const tot = data.reduce((s, r) => s + r.remaining_quantity, 0)
                  const oldest = Math.max(...data.map((r) => r.aging_days), 0)
                  return (
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0} colSpan={4}>合计 / 最老</Table.Summary.Cell>
                      <Table.Summary.Cell index={1}><b>{tot.toLocaleString()} 吨</b></Table.Summary.Cell>
                      <Table.Summary.Cell index={2}><b>{oldest} 天</b></Table.Summary.Cell>
                    </Table.Summary.Row>
                  )
                }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card
            title={
              <span>
                <ExperimentOutlined style={{ color: '#722ed1', marginRight: 8 }} />
                配煤建议（按"综合评分 + 库龄"优先级排序，建议优先用顶部批次）
              </span>
            }
            loading={loading}
          >
            {blending.length === 0 ? <Empty description="尚无在库批次" /> : (
              <Table<BlendingAdviceItem>
                dataSource={blending} rowKey="stockin_no" size="small" pagination={false}
                scroll={{ x: 1100 }}
                columns={[
                  {
                    title: '排序', width: 60, align: 'center',
                    render: (_, __, i) => i < 3
                      ? <Tag color={['gold', '#adb5bd', '#cd7f32'][i]}>TOP{i + 1}</Tag>
                      : i + 1,
                  },
                  { title: '入场单号', dataIndex: 'stockin_no', width: 150 },
                  { title: '堆区', dataIndex: 'yard_name', ellipsis: true, width: 130 },
                  { title: '煤种', dataIndex: 'coal_type', width: 80 },
                  { title: '剩余(吨)', dataIndex: 'remaining_quantity', width: 90,
                    render: (v: number) => v.toLocaleString() },
                  { title: '热值', dataIndex: 'calorific_value', width: 90,
                    render: (v: number | null) => v ?? '-' },
                  {
                    title: '库龄', dataIndex: 'aging_days', width: 80,
                    render: (v: number) => <Tag color={v > 30 ? 'red' : v > 15 ? 'orange' : 'green'}>{v} 天</Tag>,
                  },
                  {
                    title: '综合评分', dataIndex: 'current_score', width: 130,
                    render: (v: number) => (
                      <Progress percent={v} size="small"
                        strokeColor={v >= 80 ? '#52c41a' : v >= 65 ? '#1677ff' : v >= 50 ? '#faad14' : '#ff4d4f'}
                        format={(p) => `${p?.toFixed?.(1) ?? p}`}
                      />
                    ),
                  },
                  { title: '基础', dataIndex: 'base_score', width: 70,
                    render: (v: number) => v.toFixed(1) },
                  { title: '库龄扣分', dataIndex: 'aging_decay', width: 90,
                    render: (v: number) => <span style={{ color: v < 0 ? '#ff4d4f' : undefined }}>{v.toFixed(1)}</span> },
                  { title: '优先级', dataIndex: 'priority', width: 80,
                    render: (v: number) => <b style={{ color: '#722ed1' }}>{v.toFixed(1)}</b> },
                ]}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="堆区状态详情" loading={loading} size="small">
            <Row gutter={[12, 12]}>
              {yardUtil.map((y) => (
                <Col key={y.yard_code} xs={24} sm={12} lg={8} xl={6}>
                  <Card size="small" style={{ background: '#fafafa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span><b>{y.yard_code}</b> · {y.yard_name}</span>
                      <Tag color={y.status === 'ACTIVE' ? 'green' : 'orange'}>
                        {y.status === 'ACTIVE' ? '正常' : '检修'}
                      </Tag>
                    </div>
                    <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
                      {y.coal_type} · {y.inventory.toLocaleString()} / {y.capacity.toLocaleString()} 吨
                    </div>
                    <Progress
                      percent={y.utilization} size="small"
                      strokeColor={y.utilization >= 90 ? '#ff4d4f' : y.utilization >= 70 ? '#faad14' : '#13a397'}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  )
}
