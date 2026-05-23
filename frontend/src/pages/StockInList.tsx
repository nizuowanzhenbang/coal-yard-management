import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  DatePicker, message, Descriptions, Row, Col, InputNumber, Tooltip, Alert,
  Progress, Statistic,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlusOutlined, ReloadOutlined, EyeOutlined,
  DownloadOutlined, SyncOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { stockInApi, yardApi } from '../api'
import type { StockIn, StockInDetail, CoalYard } from '../types'
import { useAuthStore, canWrite } from '../stores/auth'

export default function StockInList() {
  const role = useAuthStore((s) => s.role)
  const writable = canWrite(role)

  const [data, setData] = useState<StockIn[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ yard_id?: number; coal_type?: string; order_no?: string; has_remaining?: boolean }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<StockInDetail | null>(null)
  const [yards, setYards] = useState<CoalYard[]>([])
  const [form] = Form.useForm()
  const [selectedYardId, setSelectedYardId] = useState<number | null>(null)

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const res = await stockInApi.list({ page: p, page_size: ps, ...f })
      setData(res.data.items); setTotal(res.data.total)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => {
    load(1, 20, {})
    yardApi.list({ page: 1, page_size: 100, status: 'ACTIVE' }).then((r) => setYards(r.data.items))
  }, [])

  const handleCreate = async (values: { stocked_at: dayjs.Dayjs } & Partial<StockIn>) => {
    try {
      await stockInApi.create({
        ...values,
        stocked_at: values.stocked_at.toISOString(),
      } as Partial<StockIn>)
      message.success('入场已登记')
      setCreateOpen(false); form.resetFields(); setSelectedYardId(null); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const openDetail = async (row: StockIn) => {
    try {
      const res = await stockInApi.get(row.id)
      setDetail(res.data)
    } catch {
      message.error('详情加载失败')
    }
  }

  const handleSyncQuality = async (id: number) => {
    try {
      await stockInApi.syncQuality(id)
      message.success('已同步')
      const res = await stockInApi.get(id)
      setDetail(res.data); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '同步失败')
    }
  }

  const handleExport = async () => {
    try { await stockInApi.exportCsv(filters) }
    catch (e: unknown) { message.error((e as Error)?.message || '导出失败') }
  }

  const selectedYard = yards.find((y) => y.id === selectedYardId)
  const remainingCapacity = selectedYard
    ? selectedYard.capacity - (selectedYard.current_inventory || 0)
    : null

  const columns: ColumnsType<StockIn> = [
    { title: '入场单号', dataIndex: 'stockin_no', width: 160 },
    { title: '堆区', dataIndex: 'yard_name', width: 110 },
    { title: '煤种', dataIndex: 'coal_type', width: 90 },
    {
      title: '入场量(吨)', dataIndex: 'quantity', width: 100,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '剩余(吨)', dataIndex: 'remaining_quantity', width: 100,
      render: (v: number) => v > 0 ? v.toLocaleString() : <span style={{ color: '#999' }}>已耗尽</span>,
    },
    {
      title: '库龄', dataIndex: 'aging_days', width: 80,
      render: (v: number | null) => v == null ? '-'
        : <Tag color={v > 30 ? 'red' : v > 15 ? 'orange' : 'green'}>{v} 天</Tag>,
    },
    { title: '供应商', dataIndex: 'supplier_name', ellipsis: true, width: 180 },
    {
      title: '入场时间', dataIndex: 'stocked_at', width: 140,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作', width: 70,
      render: (_, r) => <Button type="link" icon={<EyeOutlined />} onClick={() => openDetail(r)} />,
    },
  ]

  return (
    <div>
      <Card>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Space>
              <Tooltip title={writable ? '' : '当前角色无登记权限'}>
                <Button type="primary" icon={<PlusOutlined />}
                  disabled={!writable} onClick={() => setCreateOpen(true)}>登记入场</Button>
              </Tooltip>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>CSV 导出</Button>
            </Space>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <Select placeholder="堆区" allowClear style={{ width: 150 }}
                options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}` }))}
                onChange={(v) => { const next = { ...filters, yard_id: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Input placeholder="订单号" style={{ width: 180 }} allowClear
                onChange={(e) => setFilters((f) => ({ ...f, order_no: e.target.value || undefined }))}
                onPressEnter={() => { setPage(1); load(1, pageSize) }}
              />
              <Select placeholder="状态" allowClear style={{ width: 130 }}
                options={[
                  { value: true, label: '有剩余' },
                  { value: false, label: '已耗尽' },
                ]}
                onChange={(v) => { const next = { ...filters, has_remaining: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); setPage(1); load(1, pageSize, {}) }}>
                重置
              </Button>
            </Space>
          </Col>
        </Row>
        <Table<StockIn>
          dataSource={data} columns={columns} rowKey="id" loading={loading}
          scroll={{ x: 1200 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      {/* 创建 */}
      <Modal title="登记入场" open={createOpen}
        onCancel={() => { setCreateOpen(false); setSelectedYardId(null) }}
        onOk={() => form.submit()} width={720}>
        <Form form={form} layout="vertical" onFinish={handleCreate}
          initialValues={{ stocked_at: dayjs() }}
          onValuesChange={(changed) => {
            if (changed.yard_id) {
              setSelectedYardId(changed.yard_id)
              const y = yards.find((it) => it.id === changed.yard_id)
              if (y) form.setFieldsValue({ coal_type: y.designated_coal_type })
            }
          }}>
          {selectedYard && remainingCapacity != null && (
            <Alert
              type={remainingCapacity > 0 ? 'info' : 'error'}
              showIcon
              message={`${selectedYard.name}（${selectedYard.designated_coal_type}）当前库存 ${selectedYard.current_inventory?.toLocaleString()} / ${selectedYard.capacity.toLocaleString()} 吨，剩余容量 ${remainingCapacity.toLocaleString()} 吨`}
              style={{ marginBottom: 16 }}
            />
          )}
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="yard_id" label="堆区" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="label"
                  options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}（${y.designated_coal_type}）` }))}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="coal_type" label="煤种" rules={[{ required: true }]}>
                <Input disabled placeholder="选择堆区后自动填充" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="quantity" label="入场量（吨）" rules={[{ required: true }]}>
                <InputNumber min={0.1} precision={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}>
              <Form.Item name="order_no" label="采购订单号（可选）"
                tooltip="填写后将自动从采购系统拉煤质数据">
                <Input placeholder="PO-YYYYMMDD-NNNN" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="supplier_name" label="供应商">
                <Input />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="stocked_at" label="入场时间" rules={[{ required: true }]}>
                <DatePicker showTime style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={6}>
              <Form.Item name="transport_mode" label="运输方式">
                <Select options={[{ value: '铁路', label: '铁路' }, { value: '汽运', label: '汽运' }, { value: '水运', label: '水运' }]} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="calorific_value" label="热值 kcal/kg">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="ash" label="灰分 %">
                <InputNumber min={0} precision={2} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="sulfur" label="硫分 %">
                <InputNumber min={0} precision={3} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情 */}
      <Modal title={detail ? `入场详情 - ${detail.stockin_no}` : ''}
        open={!!detail} onCancel={() => setDetail(null)} width={780}
        footer={detail ? (
          <Space>
            {detail.order_no && writable && (
              <Button icon={<SyncOutlined />} onClick={() => handleSyncQuality(detail.id)}>
                同步煤质数据
              </Button>
            )}
            <Button onClick={() => setDetail(null)}>关闭</Button>
          </Space>
        ) : null}>
        {detail && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="入场单号">{detail.stockin_no}</Descriptions.Item>
            <Descriptions.Item label="堆区">{detail.yard_name}</Descriptions.Item>
            <Descriptions.Item label="煤种">{detail.coal_type}</Descriptions.Item>
            <Descriptions.Item label="入场量">{detail.quantity.toLocaleString()} 吨</Descriptions.Item>
            <Descriptions.Item label="剩余量">{detail.remaining_quantity.toLocaleString()} 吨</Descriptions.Item>
            <Descriptions.Item label="库龄">
              {detail.aging_days != null
                ? <Tag color={detail.aging_days > 30 ? 'red' : detail.aging_days > 15 ? 'orange' : 'green'}>{detail.aging_days} 天</Tag>
                : <span style={{ color: '#999' }}>已耗尽</span>}
            </Descriptions.Item>
            <Descriptions.Item label="订单号">{detail.order_no || '-'}</Descriptions.Item>
            <Descriptions.Item label="合同号">{detail.contract_no || '-'}</Descriptions.Item>
            <Descriptions.Item label="供应商" span={2}>{detail.supplier_name || '-'}</Descriptions.Item>
            <Descriptions.Item label="入场时间">{dayjs(detail.stocked_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            <Descriptions.Item label="登记人">{detail.operator || '-'}</Descriptions.Item>
            <Descriptions.Item label="运输方式">{detail.transport_mode || '-'}</Descriptions.Item>
            <Descriptions.Item label="化验数据">
              {detail.quality_synced
                ? <Tag color="green">已同步化验系统</Tag>
                : <Tag>人工录入</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="热值">{detail.calorific_value || '-'} kcal/kg</Descriptions.Item>
            <Descriptions.Item label="灰分">{detail.ash != null ? `${detail.ash}%` : '-'}</Descriptions.Item>
            <Descriptions.Item label="硫分">{detail.sulfur != null ? `${detail.sulfur}%` : '-'}</Descriptions.Item>
            <Descriptions.Item label="水分">{detail.moisture != null ? `${detail.moisture}%` : '-'}</Descriptions.Item>
            {detail.notes && (
              <Descriptions.Item label="备注" span={2}>{detail.notes}</Descriptions.Item>
            )}
          </Descriptions>
        )}
        {detail && (
          <Card size="small" title="入煤综合评分（含库龄衰减）" style={{ marginTop: 16 }}>
            <Row gutter={16} align="middle">
              <Col span={8}>
                <Statistic
                  title="当前评分"
                  value={detail.score}
                  precision={1}
                  suffix="/ 100"
                  valueStyle={{
                    color: detail.score >= 80 ? '#52c41a'
                      : detail.score >= 65 ? '#1677ff'
                      : detail.score >= 50 ? '#faad14' : '#ff4d4f',
                  }}
                />
                <Progress percent={detail.score} size="small" showInfo={false}
                  strokeColor={detail.score >= 80 ? '#52c41a'
                    : detail.score >= 65 ? '#1677ff'
                    : detail.score >= 50 ? '#faad14' : '#ff4d4f'} />
              </Col>
              <Col span={16}>
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="热值基础分">{detail.score_breakdown.calorific_score}</Descriptions.Item>
                  <Descriptions.Item label="灰分扣分">{detail.score_breakdown.ash_penalty}</Descriptions.Item>
                  <Descriptions.Item label="硫分扣分">{detail.score_breakdown.sulfur_penalty}</Descriptions.Item>
                  <Descriptions.Item label="水分扣分">{detail.score_breakdown.moisture_penalty}</Descriptions.Item>
                  <Descriptions.Item label="基础分小计">{detail.score_breakdown.base_score}</Descriptions.Item>
                  <Descriptions.Item label="库龄衰减">
                    <span style={{ color: detail.score_breakdown.aging_decay < 0 ? '#ff4d4f' : undefined }}>
                      {detail.score_breakdown.aging_decay}
                    </span>
                  </Descriptions.Item>
                </Descriptions>
              </Col>
            </Row>
          </Card>
        )}
      </Modal>
    </div>
  )
}
