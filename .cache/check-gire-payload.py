import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.routes import payload_proyeccion

app = create_app()
payload = {
    'id': 41,
    'cliente': 'Gire',
    'campania': 'Gire',
    'year': '2026',
    'mes': '2026-12',
    'jornadas': [
        {'dotacion_requerida': 11, 'carga_semanal': 'L a V', 'carga_horaria': 6},
        {'dotacion_requerida': 6, 'carga_semanal': 'S', 'carga_horaria': 5},
    ],
    'porcentaje_cumplimiento': '95',
    'dias_objetivo_manual': '',
    'horas_requeridas_override': '',
    'tipo_plp': '',
}
with app.app_context():
    result = payload_proyeccion(payload)
    print({'errores': result['errores'], 'valores': result['valores']})
