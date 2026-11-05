import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app, get_repository
from app.models import READING_PAYLOAD_ADAPTER
from app.repository import ReadingRepository


def test_dashboard_and_assets_are_served():
    with TestClient(app) as client:
        page = client.get('/')
        assert page.status_code == 200
        assert 'Estação Viva' in page.text
        assert 'theme-select' in page.text
        for asset in ['style.css', 'app.js', 'theme.js']:
            assert client.get('/assets/' + asset).status_code == 200
        assert client.get('/assets/../app/settings.py').status_code == 404


def test_dashboard_history_covers_twelve_hours_and_keeps_partial_values(tmp_path):
    repository = ReadingRepository(tmp_path / 'dashboard.db')
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    payload = READING_PAYLOAD_ADAPTER.validate_json(json.dumps({
        'schema_version': 2, 'device_id': 'station-01', 'captured_at': None,
        'temperature_c': 24.8, 'humidity_pct': None, 'pressure_hpa': 1012.8,
        'gas_raw': 812, 'light_raw': 2200, 'light_detected': None,
        'rain_detected': False,
    }))
    excluded = repository.save(payload, received_at=now-timedelta(hours=13))
    old = repository.save(payload, received_at=now-timedelta(hours=11))
    # More than the legacy history endpoint's 500-message limit.
    for i in range(510):
        latest = repository.save(payload, received_at=now-timedelta(seconds=510-i))
    future = repository.save(payload, received_at=now+timedelta(hours=1))
    app.dependency_overrides[get_repository] = lambda: repository
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/dashboard/history')
            assert response.status_code == 200
            rows = response.json()
            ids = [row['id'] for row in rows]
            assert old in ids and latest in ids
            assert excluded not in ids and future not in ids
            assert len(rows) < 10
            assert rows[0]['humidity_pct'] is None
            assert rows[0]['gas_raw'] == 812
    finally:
        app.dependency_overrides.pop(get_repository, None)
