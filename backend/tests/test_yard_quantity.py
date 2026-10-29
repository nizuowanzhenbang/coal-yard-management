"""库存数量输入在三个业务入口一致限制；使用实际HTTP验证。"""
import pytest
from tests.test_stockout_evidence import api  # noqa: F401
from app.models.user import User, UserRole

@pytest.fixture
def operator(api):
    with api.factory() as db:
        user = db.query(User).filter_by(username='viewer-test').one()
        user.role = UserRole.OPERATOR
        db.commit()
    return api

@pytest.mark.parametrize('endpoint,field,base', [
    ('stock-in','quantity',{'yard_id':999,'coal_type':'coal','stocked_at':'2026-10-28T08:00:00'}),
    ('stock-out','quantity',{'yard_id':999,'coal_type':'coal','destination':'模拟','delivered_at':'2026-10-28T08:00:00'}),
    ('stocktake','actual_inventory',{'yard_id':999,'measured_at':'2026-10-28T08:00:00'}),
])
@pytest.mark.parametrize('value', [-1, True, 0.0001, 1000000000001, 'NaN', 'Infinity'])
def test_invalid_quantity_is_422(operator, endpoint, field, base, value):
    response = operator.client.post('/api/'+endpoint, json={**base, field:value}, headers=operator.headers)
    assert response.status_code == 422, response.text

@pytest.mark.parametrize('endpoint,base', [
    ('stock-in',{'yard_id':999,'coal_type':'coal','quantity':0,'stocked_at':'2026-10-28T08:00:00'}),
    ('stock-out',{'yard_id':999,'coal_type':'coal','quantity':0,'destination':'模拟','delivered_at':'2026-10-28T08:00:00'}),
])
def test_zero_movement_rejected(operator, endpoint, base):
    assert operator.client.post('/api/'+endpoint, json=base, headers=operator.headers).status_code == 422

def test_zero_stocktake_is_valid_input(operator):
    response = operator.client.post('/api/stocktake', json={'yard_id':999, 'actual_inventory':0,
                                    'measured_at':'2026-10-28T08:00:00'}, headers=operator.headers)
    assert response.status_code == 404, response.text


def test_smallest_valid_outflow_is_fully_deducted(operator):
    from app.models.stock_in import StockIn
    import json
    with operator.factory() as db:
        incoming = db.get(StockIn, operator.in_id)
        yard_id = incoming.yard_id
    body = {'yard_id': yard_id, 'coal_type':'coal', 'quantity':0.001,
            'destination':'模拟', 'delivered_at':'2026-10-28T08:00:00'}
    result = operator.client.post('/api/stock-out', json=body, headers=operator.headers)
    assert result.status_code == 200, result.text
    assert json.loads(result.json()['data']['fifo_breakdown'])[0]['taken'] == 0.001
    with operator.factory() as db:
        assert db.get(StockIn, operator.in_id).remaining_quantity == 6.999


def test_cannot_take_tolerance_over_available_inventory(operator):
    from app.models.stock_in import StockIn
    with operator.factory() as db:
        yard_id = db.get(StockIn, operator.in_id).yard_id
    body = {'yard_id': yard_id, 'coal_type':'coal', 'quantity':7.001,
            'destination':'模拟', 'delivered_at':'2026-10-28T08:00:00'}
    assert operator.client.post('/api/stock-out', json=body, headers=operator.headers).status_code == 400


@pytest.mark.parametrize('value', ['0.0010000000000000001', '999999999999.99999', '1e-400'])
def test_precise_numeric_strings_do_not_round_into_valid_values(operator, value):
    response = operator.client.post('/api/stocktake', json={'yard_id':999, 'actual_inventory':value,
                                    'measured_at':'2026-10-28T08:00:00'}, headers=operator.headers)
    assert response.status_code == 422


def test_fifo_across_batches_maintains_sum(operator):
    from app.models.stock_in import StockIn
    from datetime import datetime
    import json
    with operator.factory() as db:
        first = db.get(StockIn, operator.in_id)
        first.remaining_quantity = 0.001
        db.add(StockIn(stockin_no='IN-2', yard_id=first.yard_id, coal_type='coal', quantity=10,
                       remaining_quantity=2, stocked_at=datetime(2026,10,28,7)))
        yard_id = first.yard_id
        db.commit()
    body = {'yard_id':yard_id, 'coal_type':'coal', 'quantity':1.001, 'destination':'模拟',
            'delivered_at':'2026-10-28T08:00:00'}
    result = operator.client.post('/api/stock-out', json=body, headers=operator.headers)
    assert result.status_code == 200, result.text
    fifo = json.loads(result.json()['data']['fifo_breakdown'])
    assert [(x['stockin_no'], x['taken']) for x in fifo] == [('IN-1', 0.001), ('IN-2', 1.0)]
    with operator.factory() as db:
        assert [r.remaining_quantity for r in db.query(StockIn).order_by(StockIn.id)] == [0, 1]


def test_approval_rechecks_inventory_without_writing_on_failure(operator, monkeypatch):
    from app.config import settings
    from app.models.stock_in import StockIn
    from app.models.stock_out import StockOut, StockOutStatus
    monkeypatch.setattr(settings, 'LARGE_STOCKOUT_THRESHOLD', 5)
    with operator.factory() as db:
        yard_id = db.get(StockIn, operator.in_id).yard_id
    body = {'yard_id':yard_id, 'coal_type':'coal', 'quantity':6, 'destination':'模拟',
            'delivered_at':'2026-10-28T08:00:00'}
    created = operator.client.post('/api/stock-out', json=body, headers=operator.headers).json()['data']
    with operator.factory() as db:
        db.get(StockIn, operator.in_id).remaining_quantity = 5
        db.query(User).filter_by(username='viewer-test').one().role = UserRole.SUPERVISOR
        db.commit()
    result = operator.client.post(f"/api/stock-out/{created['id']}/approve", json={'approved':True}, headers=operator.headers)
    assert result.status_code == 400
    with operator.factory() as db:
        assert db.get(StockIn, operator.in_id).remaining_quantity == 5
        out = db.get(StockOut, created['id'])
        assert out.status == StockOutStatus.PENDING_APPROVAL
        assert out.approver is None
