import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  DatePicker, message, Descriptions, Row, Col, InputNumber, Tooltip, Statistic, Alert,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlusOutlined, ReloadOutlined, EyeOutlined,
  AuditOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { stocktakeApi, yardApi } from '../api'
import type { Stocktake, StocktakeStatus, CoalYard } from '../types'
import { useAuthStore, canWrite, canApprove } from '../stores/auth'

const STATUS_LABEL: Record<StocktakeStatus, { label: string; color: string }> = {
  DRAFT: { label: '草稿', color: 'default' },
  PENDING_APPROVAL: { label: '待审批', color: 'warning' },
  APPROVED: { label: '已审批', color: 'success' },
  REJECTED: { label: '已驳回', color: 'error' },
}

export default function StocktakeList() {
  const role = useAuthStore((s) => s.role)
  const writable = canWrite(role)
  const approvable = canApprove(role)

  const [data, setData] = useState<Stocktake[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ yard_id?: number; status?: StocktakeStatus }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<Stocktake | null>(null)
  const [approveOpen, setApproveOpen] = useState(false)
  const [yards, setYards] = useState<CoalYard[]>([])
  const [bookInv, setBookInv] = useState<number | null>(null)
  const [form] = Form.useForm()
  const [approveForm] = Form.useForm()

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const res = await stocktakeApi.list({ page: p, page_size: ps, ...f })
      setData(res.data.items); setTotal(res.data.total)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => {
    load(1, 20, {})
    yardApi.list({ page: 1, page_size: 100 }).then((r) => setYards(r.data.items))
  }, [])

  const handleYardChange = async (yard_id: number) => {
    try {
      const res = await stocktakeApi.bookInventory(yard_id)
      setBookInv(res.data.book_inventory)
    } catch {
      setBookInv(null)
    }
  }

  const handleCreate = async (values: { yard_id: number; actual_inventory: number; measured_at: dayjs.Dayjs; method?: string; reason?: string }) => {
    try {
      await stocktakeApi.create({
        yard_id: values.yard_id,
        actual_inventory: values.actual_inventory,
        measured_at: values.measured_at.toISOString(),
        method: values.method,
        reason: values.reason,
      })
      message.success('盘点单已提交，待主管审批')
      setCreateOpen(false); form.resetFields(); setBookInv(null); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const handleApprove = async (values: { approved: boolean; approval_notes?: string }) => {
    if (!detail) return
    try {
      const res = await stocktakeApi.approve(detail.id, values.approved, values.approval_notes)
      message.success(res.message || (values.approved ? '已审批' : '已驳回'))
      setApproveOpen(false); approveForm.resetFields(); setDetail(null); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '操作失败')
    }
  }

  const columns: ColumnsType<Stocktake> = [
    { title: '盘点单号', dataIndex: 'stocktake_no', width: 170 },
    { title: '堆区', dataIndex: 'yard_name', width: 110 },
    {
      title: '账面(吨)', dataIndex: 'book_inventory', width: 100,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '实测(吨)', dataIndex: 'actual_inventory', width: 100,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '差异', dataIndex: 'diff_quantity', width: 130,
      render: (v: number, r) => {
        const color = Math.abs(r.diff_rate) >= 3 ? '#ff4d4f' : Math.abs(r.diff_rate) >= 1 ? '#faad14' : '#52c41a'
        return <span style={{ color }}>{v >= 0 ? '+' : ''}{v.toFixed(1)} 吨 ({r.diff_rate >= 0 ? '+' : ''}{r.diff_rate}%)</span>
      },
    },
    { title: '方法', dataIndex: 'method', width: 110 },
    {
      title: '盘点时间', dataIndex: 'measured_at', width: 140,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: StocktakeStatus) => <Tag color={STATUS_LABEL[v].color}>{STATUS_LABEL[v].label}</Tag>,
    },
    {
      title: '操作', width: 70,
      render: (_, r) => <Button type="link" icon={<EyeOutlined />} onClick={() => setDetail(r)} />,
    },
  ]

  return (
    <div>
      <Card>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Tooltip title={writable ? '' : '当前角色无登记权限'}>
              <Button type="primary" icon={<PlusOutlined />}
                disabled={!writable} onClick={() => setCreateOpen(true)}>新建盘点单</Button>
            </Tooltip>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <Select placeholder="堆区" allowClear style={{ width: 150 }}
                options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}` }))}
                onChange={(v) => { const next = { ...filters, yard_id: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
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
        <Table<Stocktake>
          dataSource={data} columns={columns} rowKey="id" loading={loading}
          scroll={{ x: 1150 }}
          pagination={{
            current: page, pageSize, total, showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      <Modal title="新建盘点单" open={createOpen}
        onCancel={() => { setCreateOpen(false); setBookInv(null) }}
        onOk={() => form.submit()} width={620}>
        <Form form={form} layout="vertical" onFinish={handleCreate}
          initialValues={{ measured_at: dayjs(), method: '激光扫描' }}
          onValuesChange={(changed) => {
            if (changed.yard_id) handleYardChange(changed.yard_id)
          }}>
          <Form.Item name="yard_id" label="堆区" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label"
              options={yards.map((y) => ({ value: y.id, label: `${y.code} ${y.name}（${y.designated_coal_type}）` }))}
            />
          </Form.Item>
          {bookInv != null && (
            <Alert type="info" showIcon style={{ marginBottom: 16 }}
              message={`当前账面库存：${bookInv.toLocaleString()} 吨。请录入实测值。`}
            />
          )}
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="actual_inventory" label="实测库存（吨）" rules={[{ required: true }]}>
                <InputNumber min={0} precision={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="method" label="测量方法">
                <Select options={[
                  { value: '激光扫描', label: '激光扫描' },
                  { value: '无人机', label: '无人机' },
                  { value: '人工估算', label: '人工估算' },
                ]} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="measured_at" label="盘点时间" rules={[{ required: true }]}>
            <DatePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="reason" label="差异原因（如已知）">
            <Input.TextArea rows={3} placeholder="如：雨季水分蒸发损耗、月度盘点、运输洒落" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title={detail ? `盘点详情 - ${detail.stocktake_no}` : ''}
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
              <Descriptions.Item label="盘点单号">{detail.stocktake_no}</Descriptions.Item>
              <Descriptions.Item label="堆区">{detail.yard_name}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_LABEL[detail.status].color}>{STATUS_LABEL[detail.status].label}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="盘点时间">{dayjs(detail.measured_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="盘点人">{detail.measurer || '-'}</Descriptions.Item>
              <Descriptions.Item label="测量方法">{detail.method || '-'}</Descriptions.Item>
              <Descriptions.Item label="差异原因" span={2}>{detail.reason || '-'}</Descriptions.Item>
              {detail.approver && (
                <Descriptions.Item label="审批" span={2}>
                  {detail.approver} 于 {dayjs(detail.approved_at).format('YYYY-MM-DD HH:mm')}
                  {detail.approval_notes && <div>意见：{detail.approval_notes}</div>}
                </Descriptions.Item>
              )}
            </Descriptions>

            <Card size="small" title="盘点结果" style={{ marginTop: 16 }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic title="账面库存" value={detail.book_inventory} precision={1} suffix="吨" />
                </Col>
                <Col span={8}>
                  <Statistic title="实测库存" value={detail.actual_inventory} precision={1} suffix="吨" />
                </Col>
                <Col span={8}>
                  <Statistic title="差异"
                    value={detail.diff_quantity} precision={1} suffix={`吨 (${detail.diff_rate >= 0 ? '+' : ''}${detail.diff_rate}%)`}
                    valueStyle={{
                      color: Math.abs(detail.diff_rate) >= 3 ? '#ff4d4f'
                        : Math.abs(detail.diff_rate) >= 1 ? '#faad14' : '#52c41a',
                    }}
                    prefix={detail.diff_quantity >= 0 ? '+' : ''}
                  />
                </Col>
              </Row>
            </Card>
          </>
        )}
      </Modal>

      <Modal title="盘点审批" open={approveOpen}
        onCancel={() => setApproveOpen(false)} onOk={() => approveForm.submit()}>
        <Form form={approveForm} layout="vertical" onFinish={handleApprove} initialValues={{ approved: true }}>
          <Alert type="warning" showIcon style={{ marginBottom: 12 }}
            message="审批通过后，将按差异比例缩放堆区所有有剩余的批次（按盘点时间点的账面为基准）"
          />
          <Form.Item name="approved" label="结果" rules={[{ required: true }]}>
            <Select options={[
              { value: true, label: <span><CheckOutlined style={{ color: '#52c41a' }} /> 通过 - 调账</span> },
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
