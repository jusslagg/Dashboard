import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
    page = client.get('/carga-datos-personal')
    data = client.get('/api/carga-datos-personal?year=2026')
    assert page.status_code == 200
    assert 'Carga de datos Personal' in page.get_data(as_text=True)
    assert '/carga-datos-personal' in page.get_data(as_text=True)
    assert data.status_code == 200
    assert data.json['success'] is True
    assert data.json['servicios'] == ['Personal CX', 'Personal', 'Personal Soporte', 'Personal SMB']
    print({'page': page.status_code, 'api': data.status_code, 'registros': len(data.json['proyecciones'])})
