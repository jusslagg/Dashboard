import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
app=create_app()
with app.test_client() as c:
    with c.session_transaction() as s:s['usuario_id']=1
    rows=c.get('/api/notificaciones-proyecciones?year=2026&mes=2026-08').get_json()['notificaciones']
    for x in sorted(rows,key=lambda x:-abs(x['impacto_facturacion']))[:8]:
        print(x['estado'],x['site'],x['cliente'],x['campania'],x['impacto_facturacion'])
        print(x['detalle'][:500])
