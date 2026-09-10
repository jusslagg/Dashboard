import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import ProformaPersonal

archivo = Path(r'C:\Users\jegil\Desktop\Proforma Proyectada Cable 08-2026.xlsx')
app = create_app()
with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
        session['csrf_token'] = 'verificacion-proforma'
    with app.app_context():
        original_commit = db.session.commit
        db.session.commit = db.session.flush
        try:
            response = client.post(
                '/api/proforma-personal/importar',
                data={'archivo': (io.BytesIO(archivo.read_bytes()), archivo.name)},
                headers={'X-CSRF-Token': 'verificacion-proforma'},
                content_type='multipart/form-data',
            )
            assert response.status_code == 200, response.get_data(as_text=True)
            data = response.get_json()
            assert data['success'] is True
            assert len(data['proformas']) == 6
            abonados = [fila for fila in data['proformas'] if fila['segmento'] == 'ABONOS']
            convergente = [fila for fila in data['proformas'] if fila['segmento'] == 'CUSTOMER CONVERGENTE']
            assert len(abonados) == 3 and all(fila['bono_porcentaje_total'] == 0 for fila in abonados)
            assert len(convergente) == 3 and all(round(fila['bono_porcentaje_total'], 2) == 5.5 for fila in convergente)
            assert any(fila['porcentaje_bono_ac'] == 0.5 for fila in convergente)
            page = client.get('/carga-datos-personal')
            assert page.status_code == 200
            assert 'BONO TOTAL K + M' in page.get_data(as_text=True)
            print({'status': response.status_code, 'filas': len(data['proformas']), 'bono_total': convergente[0]['bono_porcentaje_total']})
        finally:
            db.session.rollback()
            db.session.commit = original_commit
