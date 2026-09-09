import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
app=create_app()
with app.test_client() as client:
    with client.session_transaction() as session: session['usuario_id']=1
    rows=client.get('/api/notificaciones-proyecciones?year=2026&mes=2026-09&buscar=Personal').get_json()['notificaciones']
    for row in rows:
        print(row['cliente'], row['cantidad_servicios'], row['impacto_facturacion'], row['lectura'])
        print([(service['campania'], service['impacto_facturacion']) for service in row['servicios']])
