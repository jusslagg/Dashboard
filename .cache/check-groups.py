import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import AsignacionComercial

app = create_app()
with app.app_context():
    supervisor = AsignacionComercial.query.filter(
        AsignacionComercial.campania.ilike('%Supervisor exclusivo%')
    ).all()
    print('supervisor', [(a.id, a.cliente, a.campania, a.grupo_facturacion) for a in supervisor])

with app.test_client() as client:
    with client.session_transaction() as session:
        session['usuario_id'] = 1
    data = client.get('/api/resumen-proyeccion?year=2026').get_json()
    print('success', data.get('success'))
    print('grupos', [(g['nombre'], len(g['miembros'])) for g in data.get('grupos_filtro', [])])
    print('filas_supervisor', [
        (f.get('cliente'), f.get('campania'), f.get('tipo'))
        for f in data.get('filas_resumen', [])
        if 'supervisor exclusivo' in str(f.get('campania', '')).lower()
    ])
    for group in data.get('grupos_filtro', []):
        campaigns = {str(member['campania']).casefold() for member in group['miembros']}
        matched = sorted({
            f['campania'] for f in data.get('filas_resumen', [])
            if f.get('tipo') == 'total_campania' and str(f.get('campania', '')).casefold() in campaigns
        })
        print(group['nombre'], 'matched', matched)
    def norm(value):
        return ''.join(c for c in unicodedata.normalize('NFD', str(value or '').lower()) if unicodedata.category(c) != 'Mn')
    personal = next(g for g in data['grupos_filtro'] if g['nombre'] == 'Personal')
    def belongs(row):
        campaign_groups = [g for g in data['grupos_filtro'] if any(norm(m['campania']) == norm(row['campania']) for m in g['miembros'])]
        if campaign_groups:
            return any(g['nombre'] == 'Personal' for g in campaign_groups)
        return any(m['incluir_cliente'] and (norm(row['cliente']) == norm(m['cliente']) or norm(row['cliente']).startswith(norm(m['cliente']) + ' ')) for m in personal['miembros'])
    old = [f for f in data['filas_resumen'] if f['tipo'] == 'concepto' and norm(f['cliente']).startswith('personal')]
    new = [f for f in data['filas_resumen'] if f['tipo'] == 'concepto' and belongs(f)]
    print('personal old/new', sum(f['total'] for f in old), sum(f['total'] for f in new))
    print('missing', [(f['cliente'], f['campania'], f['concepto'], f['total']) for f in old if f not in new])
