"""Verifica que la matriz de perfiles coincida con la definición aprobada."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Usuario, permisos_perfil


CASOS = {
    ('Full', 'Controller'): ({'facturacion_total', 'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq', 'rmo_personal', 'directorio', 'proyecciones'}, (True, True, True, True)),
    ('Admin', 'Administrador'): ({'facturacion_total', 'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq', 'directorio', 'proyecciones'}, (True, True, True, True)),
    ('RMO_OPS', 'Jefe de site'): ({'facturacion_asignada'}, (False, False, False, False)),
    ('Finanzas', 'Resp Planif y ctrl'): (set(), (False, False, False, False)),
    ('Finanzas', 'Analista Planif y ctrl'): ({'facturacion_total', 'directorio', 'proyecciones'}, (False, False, False, False)),
    ('Tesorero', 'Tesoreria'): ({'proyecciones'}, (False, False, False, False)),
    ('RMO', 'COO'): ({'rmo_santander', 'rmo_multi_co', 'rmo_multi_sq', 'rmo_personal'}, (False, False, False, False)),
    ('RMO_WFM', 'WFM'): ({'rmo_multi_co', 'rmo_multi_sq', 'rmo_personal'}, (False, False, False, False)),
}


for (rol, puesto), (modulos, atributos) in CASOS.items():
    permisos = permisos_perfil(rol, puesto)
    assert permisos['modulos'] == modulos, f'Módulos incorrectos para {rol} / {puesto}'
    actuales = (permisos['cargar'], permisos['editar'], permisos['eliminar'], permisos['administrar_perfiles'])
    assert actuales == atributos, f'Atributos incorrectos para {rol} / {puesto}'

admin_entrega = Usuario(
    nombre='Admin entrega', email='admin-entrega@example.test', rol='Admin', puesto='Controller',
    permisos_personalizados=json.dumps({'entrega_desarrollo': True}),
)
assert admin_entrega.puede_ver_entrega_desarrollo
assert admin_entrega.puede_editar and admin_entrega.puede_administrar_usuarios
assert Usuario(nombre='Full', email='full@example.test', rol='Full').puede_ver_entrega_desarrollo

print(f'RBAC OK: {len(CASOS)} combinaciones representativas verificadas.')
