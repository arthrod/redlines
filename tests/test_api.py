import pytest
from fastapi.testclient import TestClient

from redlines.api import RedlinesAPI


@pytest.fixture(scope='module')
def client() -> TestClient:
    api = RedlinesAPI()
    app = api.create_app()
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get('/redlines/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'version' in data


def test_diff_endpoint(client: TestClient) -> None:
    payload = {
        'source': 'alpha beta',
        'test': 'alpha brave beta',
        'markdown_style': 'red_blue',
    }
    response = client.post('/redlines/diff', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['summary']['insertions'] == 1
    assert data['metadata']['style'] == 'red_blue'


def test_convert_endpoint(client: TestClient) -> None:
    payload = {
        'data': '<p>Hello</p>',
        'source_format': 'html',
        'target_format': 'txt',
    }
    response = client.post('/redlines/convert', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data['source_format'] == 'html'
    assert data['target_format'] == 'txt'
    assert 'Hello' in data['result']
