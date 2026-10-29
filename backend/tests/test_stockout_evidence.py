import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from uuid import uuid4
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base
from app.api.deps import get_db, create_access_token
from app.config import settings
from app.models.user import User, UserRole
from app.models.yard import CoalYard
from app.models.stock_in import StockIn
from app.models.stock_out import StockOut, StockOutStatus

@pytest.fixture
def api(tmp_path, monkeypatch):
    import os
    url = os.environ.get('YARD_TEST_DATABASE_URL', f'sqlite:///{tmp_path}/isolated.db')
    schema = None
    admin_engine = None
    if url.startswith('sqlite'):
        assert 'YARD_TEST_DATABASE_URL' not in os.environ, 'SQLite tests require their own temporary database'
        engine = create_engine(url, connect_args={'check_same_thread': False})
    else:
        assert url.startswith('postgresql+psycopg2://'), 'unsupported test database'
        schema = 'yard_test_' + uuid4().hex
        admin_engine = create_engine(url)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(username='viewer-test', hashed_password='unused', role=UserRole.VIEWER))
        yard = CoalYard(code='Y1', name='模拟', designated_coal_type='coal', capacity=1000)
        db.add(yard); db.flush()
        incoming = StockIn(stockin_no='IN-1', yard_id=yard.id, coal_type='coal', quantity=10,
                           remaining_quantity=7, stocked_at=datetime(2026,10,28,7))
        db.add(incoming); db.flush()
        breakdown = [{'stockin_no': 'IN-1', 'stocked_at': '2026-10-28T07:00:00', 'taken': 3,
                       'remaining_after': 7}]
        outgoing = StockOut(stockout_no='OUT-1', yard_id=yard.id, coal_type='coal', quantity=3,
                           destination='#1机组', delivered_at=datetime(2026,10,28,8),
                           fifo_breakdown=json.dumps(breakdown), status=StockOutStatus.COMPLETED)
        db.add(outgoing); db.commit()
        out_id, in_id = outgoing.id, incoming.id
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.setitem(settings.__dict__, 'YARD_SOURCE_INSTANCE', 'synthetic-yard')
    client = TestClient(app)
    headers = {'Authorization': 'Bearer '+create_access_token('viewer-test')}
    yield SimpleNamespace(client=client, headers=headers, factory=factory, out_id=out_id, in_id=in_id,
                          path=f'/api/stock-out/{out_id}/accounting-evidence',
                          body={'offset_minutes': 480, 'time_evidence': '模拟UTC+08记录'}, breakdown=breakdown)
    app.dependency_overrides.clear()
    if schema is None:
        Base.metadata.drop_all(engine)
    engine.dispose()
    if admin_engine is not None:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()

def test_readonly_export_and_stable_digest(api):
    assert api.client.post(api.path, json=api.body).status_code == 401
    result = api.client.post(api.path, json=api.body, headers=api.headers)
    assert result.status_code == 200, result.text
    data = result.json()['data']
    assert data['evidence_kind'] == 'inventory_fifo_accounting'
    assert data['verification_scope'] == 'current_database_state_only'
    assert data['historical_source_identity_verified'] is False
    assert data['source_instance'] == 'synthetic-yard'
    assert data['quantity_tonnes'] == '3.000'
    assert data['delivered_at'] == '2026-10-28T08:00:00+08:00'
    assert data['destination_text'] == '#1机组'
    assert data['fifo'][0]['stockin_id'] == str(api.in_id)
    assert data['fifo'][0]['quantity_tonnes'] == '3.000'
    assert data['time_provenance']['declared_by'] == 'viewer-test'
    assert len(data['content_sha256']) == 64
    assert api.client.post(api.path, json=api.body, headers=api.headers).json()['data'] == data
    changed = api.client.post(api.path, json={**api.body, 'time_evidence':'不同说明'}, headers=api.headers).json()['data']
    assert changed['content_sha256'] != data['content_sha256']
    with api.factory() as db:
        assert db.get(StockIn, api.in_id).remaining_quantity == 7
        assert db.query(StockOut).count() == 1

@pytest.mark.parametrize('change', ['pending','empty','bad_json','duplicate','sum','zero','negative','fraction','missing','wrong_yard','future','wrong_time','negative_remainder','duplicate_keys'])
def test_reject_inconsistent_accounting(api, change):
    with api.factory() as db:
        row = db.get(StockOut, api.out_id)
        items = api.breakdown
        if change == 'pending': row.status = StockOutStatus.PENDING_APPROVAL
        elif change == 'empty': items = []
        elif change == 'duplicate': items = items * 2; row.quantity = 6
        elif change == 'sum': row.quantity = 4
        elif change == 'zero': row.quantity = 0
        elif change == 'negative': row.quantity = -1
        elif change == 'fraction': row.quantity = 3.0001
        elif change == 'missing': items[0]['stockin_no'] = 'missing'
        elif change == 'wrong_yard': row.coal_type = 'other'
        elif change == 'future': row.delivered_at = datetime(2026,10,28,6)
        elif change == 'wrong_time': items[0]['stocked_at'] = '2026-10-28T06:00:00'
        elif change == 'negative_remainder': items[0]['remaining_after'] = -1
        row.fifo_breakdown = json.dumps(items)
        if change == 'bad_json': row.fifo_breakdown = 'bad'
        if change == 'duplicate_keys': row.fifo_breakdown = '[{"stockin_no":"bad","stockin_no":"IN-1","stocked_at":"2026-10-28T07:00:00","taken":3,"remaining_after":7}]'
        db.commit()
    result = api.client.post(api.path, json=api.body, headers=api.headers)
    assert result.status_code == 409, result.text

@pytest.mark.parametrize('body', [{}, {'offset_minutes':True,'time_evidence':'x'}, {'offset_minutes':841,'time_evidence':'x'}, {'offset_minutes':480,'time_evidence':' '}, {'offset_minutes':480,'time_evidence':'x\x00y'}])
def test_invalid_time_declaration(api, body):
    assert api.client.post(api.path, json=body, headers=api.headers).status_code == 422

def test_missing_source_instance(api, monkeypatch):
    monkeypatch.setitem(settings.__dict__, 'YARD_SOURCE_INSTANCE', '')
    assert api.client.post(api.path, json=api.body, headers=api.headers).status_code == 503


def test_out_of_range_id_rejected(api):
    response = api.client.post('/api/stock-out/999999999999999999999999999/accounting-evidence', json=api.body, headers=api.headers)
    assert response.status_code == 422


def test_deeply_corrupt_fifo_is_rejected(api):
    with api.factory() as db:
        db.get(StockOut, api.out_id).fifo_breakdown = '[' * 12000 + ']' * 12000
        db.commit()
    assert api.client.post(api.path, json=api.body, headers=api.headers).status_code == 409
