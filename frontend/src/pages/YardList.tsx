import { useState, useEffect, useCallback } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select,
  message, Descriptions, Row, Col, InputNumber, Progress, Tooltip, Statistic,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  PlusOutlined, ReloadOutlined, EyeOutlined,
  DownloadOutlined, ToolOutlined, StopOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { yardApi } from '../api'
import type { CoalYard, CoalYardDetail, YardStatus } from '../types'
import { useAuthStore, canWrite, canApprove } from '../stores/auth'

const STATUS_LABEL: Record<YardStatus, { label: string; color: string }> = {
  ACTIVE: { label: '正常', color: 'success' },
  MAINTENANCE: { label: '检修中', color: 'warning' },
  DISABLED: { label: '已停用', color: 'default' },
}

const COAL_TYPES = ['动力煤', '长焰煤', '弱粘煤', '1/3焦煤', '褐煤', '混煤']

export default function YardList() {
  const role = useAuthStore((s) => s.role)
  const writable = canWrite(role)
  const approvable = canApprove(role)

  const [data, setData] = useState<CoalYard[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ status?: YardStatus; coal_type?: string; keyword?: string }>({})
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<CoalYardDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [form] = Form.useForm()

  const load = useCallback(async (p = page, ps = pageSize, f = filters) => {
    setLoading(true)
    try {
      const res = await yardApi.list({ page: p, page_size: ps, ...f })
      setData(res.data.items)
      setTotal(res.data.total)
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, filters])

  useEffect(() => { load(1, 20, {}) }, [])

  const openDetail = async (row: CoalYard) => {
    setDetailLoading(true)
    try {
      const res = await yardApi.get(row.id)
      setDetail(res.data)
    } catch {
      message.error('详情加载失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const handleCreate = async (values: Partial<CoalYard>) => {
    try {
      await yardApi.create(values)
      message.success('堆区已创建')
      setCreateOpen(false); form.resetFields(); load()
    } catch (e: unknown) {
      message.error((e as { detail?: string })?.detail || '创建失败')
    }
  }

  const handleExport = async () => {
    try { await yardApi.exportCsv(filters) }
    catch (e: unknown) { message.error((e as Error)?.message || '导出失败') }
  }

  const columns: ColumnsType<CoalYard> = [
    { title: '编号', dataIndex: 'code', width: 90 },
    { title: '堆区名称', dataIndex: 'name' },
    { title: '设计煤种', dataIndex: 'designated_coal_type', width: 100 },
    {
      title: '容量(吨)', dataIndex: 'capacity', width: 110,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '当前库存(吨)', dataIndex: 'current_inventory', width: 120,
      render: (v: number | null) => v != null ? v.toLocaleString() : '-',
    },
    {
      title: '利用率', dataIndex: 'utilization', width: 150,
      render: (v: number | null) => v != null
        ? <Progress percent={v} size="small"
            strokeColor={v >= 90 ? '#ff4d4f' : v >= 70 ? '#faad14' : '#13a397'} />
        : '-',
    },
    {
      title: '最老批次库龄', dataIndex: 'oldest_in_days', width: 110,
      render: (v: number | null) => v == null ? '-'
        : <Tag color={v > 30 ? 'red' : v > 15 ? 'orange' : 'green'}>{v} 天</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: YardStatus) => <Tag color={STATUS_LABEL[v].color}>{STATUS_LABEL[v].label}</Tag>,
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
                  disabled={!writable} onClick={() => setCreateOpen(true)}>新建堆区</Button>
              </Tooltip>
              <Button icon={<DownloadOutlined />} onClick={handleExport}>CSV 导出</Button>
            </Space>
          </Col>
          <Col flex="auto">
            <Space wrap>
              <Input placeholder="编号/名称" style={{ width: 180 }} allowClear
                onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value || undefined }))}
                onPressEnter={() => { setPage(1); load(1, pageSize) }}
              />
              <Select placeholder="状态" allowClear style={{ width: 120 }}
                options={Object.entries(STATUS_LABEL).map(([v, { label }]) => ({ value: v, label }))}
                onChange={(v) => { const next = { ...filters, status: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Select placeholder="煤种" allowClear style={{ width: 130 }}
                options={COAL_TYPES.map((c) => ({ value: c, label: c }))}
                onChange={(v) => { const next = { ...filters, coal_type: v }; setFilters(next); setPage(1); load(1, pageSize, next) }}
              />
              <Button icon={<ReloadOutlined />} onClick={() => { setFilters({}); setPage(1); load(1, pageSize, {}) }}>
                重置
              </Button>
            </Space>
          </Col>
        </Row>
        <Table<CoalYard>
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
      <Modal title="新建煤场堆区" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()} width={680}>
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="name" label="堆区名称" rules={[{ required: true }]}>
                <Input placeholder="如：一号堆区" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="designated_coal_type" label="设计煤种" rules={[{ required: true }]}>
                <Select options={COAL_TYPES.map((c) => ({ value: c, label: c }))} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="capacity" label="设计容量（吨）" rules={[{ required: true }]}>
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="location" label="位置">
                <Input placeholder="厂区东南角" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="longitude" label="经度">
                <InputNumber precision={4} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="latitude" label="纬度">
                <InputNumber precision={4} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 详情 */}
      <Modal
        title={detail ? `堆区详情 - ${detail.code} ${detail.name}` : ''}
        open={!!detail}
        onCancel={() => setDetail(null)}
        width={780}
        confirmLoading={detailLoading}
        footer={detail ? (
          <Space>
            {detail.status === 'ACTIVE' && approvable && (
              <Button icon={<ToolOutlined />} onClick={async () => {
                await yardApi.maintenance(detail.id)
                message.success('已置为检修')
                setDetail(null); load()
              }}>置为检修</Button>
            )}
            {detail.status === 'MAINTENANCE' && approvable && (
              <Button type="primary" icon={<CheckCircleOutlined />} onClick={async () => {
                await yardApi.activate(detail.id)
                message.success('已恢复使用')
                setDetail(null); load()
              }}>恢复使用</Button>
            )}
            {detail.status !== 'DISABLED' && approvable && (
              <Button danger icon={<StopOutlined />} onClick={() => {
                Modal.confirm({
                  title: '确认停用堆区？', content: '需先清空库存',
                  onOk: async () => {
                    try {
                      await yardApi.disable(detail.id)
                      message.success('已停用')
                      setDetail(null); load()
                    } catch (e: unknown) {
                      message.error((e as { detail?: string })?.detail || '操作失败')
                    }
                  },
                })
              }}>停用</Button>
            )}
            <Button onClick={() => setDetail(null)}>关闭</Button>
          </Space>
        ) : null}
      >
        {detail && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="编号">{detail.code}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_LABEL[detail.status].color}>{STATUS_LABEL[detail.status].label}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="名称" span={2}>{detail.name}</Descriptions.Item>
              <Descriptions.Item label="设计煤种">{detail.designated_coal_type}</Descriptions.Item>
              <Descriptions.Item label="设计容量">{detail.capacity.toLocaleString()} 吨</Descriptions.Item>
              <Descriptions.Item label="当前库存">{detail.current_inventory?.toLocaleString()} 吨</Descriptions.Item>
              <Descriptions.Item label="利用率">{detail.utilization}%</Descriptions.Item>
              <Descriptions.Item label="位置" span={2}>{detail.location || '-'}</Descriptions.Item>
              <Descriptions.Item label="坐标" span={2}>
                {detail.longitude && detail.latitude ? `${detail.longitude}, ${detail.latitude}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="批次数">{detail.batch_count}</Descriptions.Item>
              <Descriptions.Item label="最老库龄">
                {detail.oldest_in_days != null ? `${detail.oldest_in_days} 天` : '-'}
              </Descriptions.Item>
            </Descriptions>

            <Card size="small" title="库龄分布（FIFO 批次剩余量）" style={{ marginTop: 16 }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic title="正常 (≤15 天)" value={detail.aging_summary.green} precision={1} suffix="吨"
                    valueStyle={{ color: '#52c41a' }} />
                </Col>
                <Col span={8}>
                  <Statistic title="预警 (15-30 天)" value={detail.aging_summary.yellow} precision={1} suffix="吨"
                    valueStyle={{ color: '#faad14' }} />
                </Col>
                <Col span={8}>
                  <Statistic title="危险 (>30 天)" value={detail.aging_summary.red} precision={1} suffix="吨"
                    valueStyle={{ color: '#ff4d4f' }} />
                </Col>
              </Row>
            </Card>
          </>
        )}
      </Modal>
    </div>
  )
}
