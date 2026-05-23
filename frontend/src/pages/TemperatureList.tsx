import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  DatePicker, message, Row, Col, InputNumber, Tooltip, Alert, Statistic, Empty,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  FireOutlined, LineChartOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import dayjs from 'dayjs'
import { temperatureApi, yardApi } from '../api'
import type { TemperatureReading, TempTrendItem, TemperatureSource, TempLevel, CoalYard } from '../types'
import { useAuthStore, canWrite } from '../stores/auth'

const LEVEL_LABEL: Record<TempLevel, { label: string; color: string }> = {
  green: { label: '正常', color: 'success' },
  warn: { label: '预警', color: 'gold' },
  alert: { label: '告警', color: 'orange' },
  danger: { label: '危险', color: 'red' },
}

const SOURCE_LABEL: Record<TemperatureSource, string> = {
  MANUAL: '人工红外',
  SENSOR: '在线传感器',
  THERMAL_IMAGE: '热成像',
}

const SPOT_OPTIONS = ['东南角', '东北角', '西南角', '西北角', '中部', '堆顶', '堆脚']

export default function TemperatureList() {
  const role = useAuthStore((s) => s.role)
  const writable = canWrite(role)

  const [data, setData] = useState<TemperatureReading[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ yard_id?: number; min_temp?: number }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [hotspots, setHotspots] = useState<TemperatureReading[]>([])
  const [trendYardId, setTrendYardId] = useState<number | null>(null)
  const [trend, setTrend] = useState<TempTrendItem[]>([])
  const [yards, setYards] = useState<CoalYard[]>([])
  const [form] = Form.useForm()

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const [list, hs] = await Promise.all([
        temperatureApi.list({ page: p, page_size: ps, ...f }),
        temperatureApi.hotspots(10),
      ])
      setData(list.data.items); setTotal(list.data.total)
      setHotspots(hs.data)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => {
    load(1, 20, {})
    yardApi.list({ page: 1, page_size: 100, status: 'ACTIVE' }).then((r) => {
      setYards(r.data.items)
      if (r.data.items.length > 0) setTrendYardId(r.data.items[0].id)
    })
  }, [])

  useEffect(() => {
    if (trendYardId) {
      temperatureApi.trend(trendYardId, 7).then((r) => setTrend(r.data))
    }
  }, [trendYardId])

  const handleCreate = async (values: { yard_id: number; spot: string; temperature: number; source: TemperatureSource; measured_at: dayjs.Dayjs; notes?: string }) => {
    try {
      const res = await temperatureApi.create({
        ...values,
        measured_at: values.measured_at.toISOString(),
      })
      message[(res.data.level === 'danger' || res.data.level === 'alert') ? 'warning' : 'success'](res.message)
      setCreateOpen(false); form.resetFields(); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除该温度记录？',
      onOk: async () => {
        await temperatureApi.remove(id)
        message.success('已删除'); load()
      },
    })
  }

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['最高', '平均', '最低'], bottom: 0 },
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((t) => t.date.slice(5)) },
    yAxis: { type: 'value', name: '℃' },
    series: [
      { name: '最高', type: 'line', data: trend.map((t) => t.max_temp), itemStyle: { color: '#ff4d4f' } },
      { name: '平均', type: 'line', data: trend.map((t) => t.avg_temp), itemStyle: { color: '#fa8c16' } },
      { name: '最低', type: 'line', data: trend.map((t) => t.min_temp), itemStyle: { color: '#13a397' } },
    ],
  }

  const columns: ColumnsType<TemperatureReading> = [
    {
      title: '级别', dataIndex: 'level', width: 80,
      render: (v: TempLevel) => <Tag color={LEVEL_LABEL[v].color}>{LEVEL_LABEL[v].label}</Tag>,
    },
    {
      title: '温度(℃)', dataIndex: 'temperature', width: 90,
      render: (v: number, r) => (
        <span style={{ fontWeight: 600, color: r.level === 'danger' ? '#ff4d4f' : r.level === 'alert' ? '#fa8c16' : r.level === 'warn' ? '#faad14' : undefined }}>
          {v.toFixed(1)}
        </span>
      ),
    },
    { title: '堆区', dataIndex: 'yard_name', width: 130 },
    { title: '测点', dataIndex: 'spot', width: 100 },
    {
      title: '来源', dataIndex: 'source', width: 110,
      render: (v: TemperatureSource) => SOURCE_LABEL[v],
    },
    {
      title: '测量时间', dataIndex: 'measured_at', width: 150,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    { title: '登记人', dataIndex: 'operator', width: 90 },
    {
      title: '操作', width: 80,
      render: (_, r) => writable && (
        <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
      ),
    },
  ]

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title={<span><FireOutlined style={{ color: '#ff4d4f', marginRight: 6 }} />24h 高温测点榜</span>}
            loading={loading} size="small">
            {hotspots.length === 0 ? <Empty description="24h 内无测温记录" />
              : <Table<TemperatureReading>
                  dataSource={hotspots} rowKey="id" size="small" pagination={false}
                  scroll={{ x: 700 }}
                  columns={[
                    {
                      title: '级别', dataIndex: 'level', width: 70,
                      render: (v: TempLevel) => <Tag color={LEVEL_LABEL[v].color}>{LEVEL_LABEL[v].label}</Tag>,
                    },
                    { title: '温度(℃)', dataIndex: 'temperature', width: 90,
                      render: (v: number) => v.toFixed(1) },
                    { title: '堆区', dataIndex: 'yard_name', ellipsis: true },
                    { title: '测点', dataIndex: 'spot', width: 100 },
                    { title: '测量时间', dataIndex: 'measured_at', width: 130,
                      render: (v: string) => dayjs(v).format('MM-DD HH:mm') },
                  ]}
                />}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            title={<span><LineChartOutlined style={{ color: '#13a397', marginRight: 6 }} />堆区温度趋势（7 天）</span>}
            size="small"
            extra={
              <Select
                value={trendYardId ?? undefined}
                style={{ width: 180 }}
                onChange={setTrendYardId}
                options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}` }))}
              />
            }
          >
            {trend.length === 0
              ? <Empty description="所选堆区暂无温度数据" />
              : <ReactECharts option={trendOption} style={{ height: 240 }} notMerge />}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="预警阈值" value={50} suffix="℃ +" valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="告警阈值" value={65} suffix="℃ +" valueStyle={{ color: '#fa8c16' }} />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic title="危险阈值（接近自燃点）" value={80} suffix="℃ +" valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
      </Row>

      <Card>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Tooltip title={writable ? '' : '当前角色无登记权限'}>
              <Button type="primary" icon={<PlusOutlined />}
                disabled={!writable} onClick={() => setCreateOpen(true)}>录入温度</Button>
            </Tooltip>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <Select placeholder="堆区" allowClear style={{ width: 150 }}
                options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}` }))}
                onChange={(v) => { const next = { ...filters, yard_id: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <InputNumber placeholder="最低温度℃" style={{ width: 130 }}
                onChange={(v) => { const next = { ...filters, min_temp: v ?? undefined }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); setPage(1); load(1, pageSize, {}) }}>
                重置
              </Button>
            </Space>
          </Col>
        </Row>
        <Table<TemperatureReading>
          dataSource={data} columns={columns} rowKey="id" loading={loading}
          scroll={{ x: 1000 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      <Modal title="录入温度测量" open={createOpen}
        onCancel={() => setCreateOpen(false)} onOk={() => form.submit()} width={620}>
        <Form form={form} layout="vertical" onFinish={handleCreate}
          initialValues={{ measured_at: dayjs(), source: 'MANUAL' }}>
          <Alert
            type="info" showIcon style={{ marginBottom: 16 }}
            message="温度阈值：≥50℃ 预警，≥65℃ 告警（应处置），≥80℃ 危险（接近自燃点）"
          />
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="yard_id" label="堆区" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="label"
                  options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}` }))}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="spot" label="测点位置" rules={[{ required: true }]}>
                <Select mode="tags" maxCount={1}
                  options={SPOT_OPTIONS.map((s) => ({ value: s, label: s }))}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="temperature" label="温度（℃）" rules={[{ required: true }]}>
                <InputNumber min={-50} max={500} precision={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="source" label="测量方式" rules={[{ required: true }]}>
                <Select options={Object.entries(SOURCE_LABEL).map(([v, l]) => ({ value: v, label: l }))} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="measured_at" label="测量时间" rules={[{ required: true }]}>
                <DatePicker showTime style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} placeholder="如：测温后已采取倒堆/洒水措施" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
