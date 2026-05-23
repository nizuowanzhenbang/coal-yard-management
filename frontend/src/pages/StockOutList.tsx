import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  DatePicker, message, Descriptions, Row, Col, InputNumber, Tooltip, Alert,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlusOutlined, ReloadOutlined, EyeOutlined, DownloadOutlined,
  AuditOutlined, CheckOutlined, CloseOutlined, WarningOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { stockOutApi, yardApi } from '../api'
import type { StockOut, StockOutStatus, CoalYard } from '../types'
import { useAuthStore, canWrite, canApprove } from '../stores/auth'

const DESTINATIONS = ['#1机组A磨', '#1机组B磨', '#2机组A磨', '#2机组B磨', '#3机组A磨', '#3机组B磨']

const STATUS_LABEL: Record<StockOutStatus, { label: string; color: string }> = {
  PENDING_APPROVAL: { label: '待审批', color: 'warning' },
  APPROVED: { label: '已通过', color: 'success' },
  REJECTED: { label: '已驳回', color: 'error' },
  COMPLETED: { label: '已完成', color: 'default' },
}

const LARGE_THRESHOLD = 5000

interface FifoEntry { stockin_no: string; stocked_at?: string; taken: number; remaining_after?: number }

export default function StockOutList() {
  const role = useAuthStore((s) => s.role)
  const writable = canWrite(role)
  const approvable = canApprove(role)

  const [data, setData] = useState<StockOut[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ yard_id?: number; coal_type?: string; destination?: string; status?: StockOutStatus }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<StockOut | null>(null)
  const [approveOpen, setApproveOpen] = useState(false)
  const [approveForm] = Form.useForm()
  const [pendingQty, setPendingQty] = useState<number | null>(null)
  const [yards, setYards] = useState<CoalYard[]>([])
  const [form] = Form.useForm()
  const [selectedYardId, setSelectedYardId] = useState<number | null>(null)

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const res = await stockOutApi.list({ page: p, page_size: ps, ...f })
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

  const handleCreate = async (values: { delivered_at: dayjs.Dayjs } & Partial<StockOut>) => {
    try {
      const res = await stockOutApi.create({
        ...values,
        delivered_at: values.delivered_at.toISOString(),
      } as Partial<StockOut>)
      message[res.data.requires_approval ? 'warning' : 'success'](res.message || '出场已登记')
      setCreateOpen(false); form.resetFields(); setSelectedYardId(null); setPendingQty(null); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const handleApprove = async (values: { approved: boolean; approval_notes?: string }) => {
    if (!detail) return
    try {
      const res = await stockOutApi.approve(detail.id, values.approved, values.approval_notes)
      message.success(res.message)
      setApproveOpen(false); approveForm.resetFields(); setDetail(null); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const handleExport = async () => {
    try { await stockOutApi.exportCsv(filters) }
    catch (e: unknown) { message.error((e as Error)?.message || '导出失败') }
  }

  const selectedYard = yards.find((y) => y.id === selectedYardId)

  const columns: ColumnsType<StockOut> = [
    { title: '出场单号', dataIndex: 'stockout_no', width: 160 },
    { title: '堆区', dataIndex: 'yard_name', width: 110 },
    { title: '煤种', dataIndex: 'coal_type', width: 90 },
    {
      title: '出场量(吨)', dataIndex: 'quantity', width: 110,
      render: (v: number, r) => (
        <span>
          {v.toLocaleString()}
          {r.requires_approval && (
            <Tooltip title="大额">
              <WarningOutlined style={{ color: '#fa541c', marginLeft: 4 }} />
            </Tooltip>
          )}
        </span>
      ),
    },
    { title: '去向', dataIndex: 'destination', width: 120 },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: StockOutStatus) => <Tag color={STATUS_LABEL[v].color}>{STATUS_LABEL[v].label}</Tag>,
    },
    {
      title: '出场时间', dataIndex: 'delivered_at', width: 140,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    { title: '登记人', dataIndex: 'operator', width: 90 },
    {
      title: '操作', width: 70,
      render: (_, r) => <Button type="link" icon={<EyeOutlined />} onClick={() => setDetail(r)} />,
    },
  ]

  let fifoEntries: FifoEntry[] = []
  if (detail?.fifo_breakdown) {
    try { fifoEntries = JSON.parse(detail.fifo_breakdown) } catch { /* ignore */ }
  }

  return (
    <div>
      <Card>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Space>
              <Tooltip title={writable ? '' : '当前角色无登记权限'}>
                <Button type="primary" icon={<PlusOutlined />}
                  disabled={!writable} onClick={() => setCreateOpen(true)}>登记出场</Button>
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
              <Input placeholder="去向（机组/磨煤机）" style={{ width: 180 }} allowClear
                onChange={(e) => setFilters((f) => ({ ...f, destination: e.target.value || undefined }))}
                onPressEnter={() => { setPage(1); load(1, pageSize) }}
              />
              <Select placeholder="状态" allowClear style={{ width: 130 }}
                options={Object.entries(STATUS_LABEL).map(([v, { label }]) => ({ value: v, label }))}
                onChange={(v) => { const next = { ...filters, status: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); setPage(1); load(1, pageSize, {}) }}>
                重置
              </Button>
            </Space>
          </Col>
        </Row>
        <Table<StockOut>
          dataSource={data} columns={columns} rowKey="id" loading={loading}
          scroll={{ x: 1100 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      <Modal title="登记出场" open={createOpen}
        onCancel={() => { setCreateOpen(false); setSelectedYardId(null) }}
        onOk={() => form.submit()} width={680}>
        <Form form={form} layout="vertical" onFinish={handleCreate}
          initialValues={{ delivered_at: dayjs(), purpose: '发电' }}
          onValuesChange={(changed, all) => {
            if (changed.yard_id) {
              setSelectedYardId(changed.yard_id)
              const y = yards.find((it) => it.id === changed.yard_id)
              if (y) form.setFieldsValue({ coal_type: y.designated_coal_type })
            }
            setPendingQty(all.quantity ?? null)
          }}>
          {selectedYard && (
            <Alert
              type="info"
              showIcon
              message={`${selectedYard.name}（${selectedYard.designated_coal_type}）当前库存 ${selectedYard.current_inventory?.toLocaleString()} 吨，将按 FIFO 从最早入场批次开始扣减`}
              style={{ marginBottom: 16 }}
            />
          )}
          {pendingQty != null && pendingQty >= LARGE_THRESHOLD && (
            <Alert
              type="warning" showIcon
              message={`大额出场（≥${LARGE_THRESHOLD} 吨）：提交后将进入"待审批"状态，主管通过后才会执行 FIFO 扣减`}
              style={{ marginBottom: 16 }}
            />
          )}
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="yard_id" label="堆区" rules={[{ required: true }]}>
                <Select showSearch optionFilterProp="label"
                  options={yards.map((y) => ({
                    value: y.id,
                    label: `${y.code} ${y.name}（剩 ${y.current_inventory?.toLocaleString() || 0} 吨）`,
                  }))}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="coal_type" label="煤种" rules={[{ required: true }]}>
                <Input disabled placeholder="选择堆区后自动填充" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="quantity" label="出场量（吨）" rules={[{ required: true }]}>
                <InputNumber min={0.1} precision={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="destination" label="去向" rules={[{ required: true }]}>
                <Select options={DESTINATIONS.map((d) => ({ value: d, label: d }))}
                  mode="tags" allowClear />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="purpose" label="用途">
                <Select options={[{ value: '发电', label: '发电' }, { value: '调试', label: '调试' }, { value: '试烧', label: '试烧' }]} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="delivered_at" label="出场时间" rules={[{ required: true }]}>
                <DatePicker showTime style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={detail ? `出场详情 - ${detail.stockout_no}` : ''}
        open={!!detail} onCancel={() => setDetail(null)} width={780}
        footer={detail ? (
          <Space>
            {detail.status === 'PENDING_APPROVAL' && approvable && (
              <Button type="primary" icon={<AuditOutlined />} onClick={() => setApproveOpen(true)}>审批</Button>
            )}
            <Button onClick={() => setDetail(null)}>关闭</Button>
          </Space>
        ) : null}>
        {detail && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="出场单号">{detail.stockout_no}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_LABEL[detail.status].color}>{STATUS_LABEL[detail.status].label}</Tag>
                {detail.requires_approval && <Tag color="orange" style={{ marginLeft: 4 }}>大额</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="堆区">{detail.yard_name}</Descriptions.Item>
              <Descriptions.Item label="煤种">{detail.coal_type}</Descriptions.Item>
              <Descriptions.Item label="出场量">{detail.quantity.toLocaleString()} 吨</Descriptions.Item>
              <Descriptions.Item label="去向">{detail.destination}</Descriptions.Item>
              <Descriptions.Item label="用途">{detail.purpose || '-'}</Descriptions.Item>
              <Descriptions.Item label="出场时间">{dayjs(detail.delivered_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="登记人">{detail.operator || '-'}</Descriptions.Item>
              {detail.approver && (
                <Descriptions.Item label="审批" span={2}>
                  {detail.approver} 于 {dayjs(detail.approved_at).format('YYYY-MM-DD HH:mm')}
                  {detail.approval_notes && <div>意见：{detail.approval_notes}</div>}
                </Descriptions.Item>
              )}
              {detail.notes && (
                <Descriptions.Item label="备注" span={2}>{detail.notes}</Descriptions.Item>
              )}
            </Descriptions>
            {detail.status === 'PENDING_APPROVAL' && fifoEntries.length === 0 && (
              <Alert
                style={{ marginTop: 16 }}
                type="warning" showIcon
                message="该单为大额待审批，库存尚未扣减；主管审批通过后将按 FIFO 自动扣减"
              />
            )}
            {fifoEntries.length > 0 && (
              <Card size="small" title="FIFO 扣减明细" style={{ marginTop: 16 }}>
                <Table<FifoEntry>
                  size="small" pagination={false} rowKey="stockin_no"
                  dataSource={fifoEntries}
                  columns={[
                    { title: '入场单号', dataIndex: 'stockin_no' },
                    { title: '入场时间', dataIndex: 'stocked_at',
                      render: (v?: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
                    { title: '扣减量(吨)', dataIndex: 'taken',
                      render: (v: number) => v.toLocaleString() },
                    { title: '扣后剩余(吨)', dataIndex: 'remaining_after',
                      render: (v?: number) => v != null ? v.toLocaleString() : '-' },
                  ]}
                />
              </Card>
            )}
          </>
        )}
      </Modal>

      <Modal title="大额出场审批" open={approveOpen}
        onCancel={() => setApproveOpen(false)} onOk={() => approveForm.submit()}>
        <Form form={approveForm} layout="vertical" onFinish={handleApprove} initialValues={{ approved: true }}>
          {detail && (
            <Alert type="warning" showIcon style={{ marginBottom: 12 }}
              message={`${detail.yard_name} · ${detail.coal_type} · ${detail.quantity.toLocaleString()} 吨 → ${detail.destination}`}
              description="审批通过后立即从该堆区按 FIFO 扣减；驳回则保留记录但不扣减"
            />
          )}
          <Form.Item name="approved" label="结果" rules={[{ required: true }]}>
            <Select options={[
              { value: true, label: <span><CheckOutlined style={{ color: '#52c41a' }} /> 通过 - 执行扣减</span> },
              { value: false, label: <span><CloseOutlined style={{ color: '#ff4d4f' }} /> 驳回</span> },
            ]} />
          </Form.Item>
          <Form.Item name="approval_notes" label="审批意见">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
