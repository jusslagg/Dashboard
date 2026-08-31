"""Alinea alias históricos inequívocos sin modificar valores numéricos."""
from datetime import datetime
from pathlib import Path
import shutil
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app import create_app, db  # noqa: E402
from app.models import AsignacionComercial, Facturacion2026, HistorialCambio  # noqa: E402

REGLAS = [
    ('Naturgy Energia San Juan', 'Naturgy Energia San Juan', 24, 'Energía San Juan'),
    ('Naturgy Energia San Juan TL', 'Naturgy Energia San Juan TL', 25, 'Energía San Juan TL'),
    ('Santander Chat', 'Santander Chat Redes', 5, 'Santander Chat Redes'),
    ('Santander Chat', 'Santander Chat', 4, 'Santander Chat'),
    ('Santander Retenciones', 'Santander Retenciones', 83, 'Retención Seguros'),
    ('Santander Retenciones Mixto SL', 'Santander Retenciones Mixto SL', 84, 'Retención Mix'),
    ('Assurant', 'BBVA - Préstamos RDI', 74, 'BBVA - Préstamos'),
]
NUMERICOS = ('horas_objetivo', 'horas_facturadas', 'valor_hora', 'facturado_horas_manual',
             'total_facturado_manual', 'variable_productivo', 'bonos', 'penalizaciones',
             'netx_gen', 'otros')

base = RAIZ / 'instance' / 'facturacion.db'
marca = datetime.now().strftime('%Y%m%d-%H%M%S')
respaldo = RAIZ / 'instance' / f'facturacion.pre-alinear-maestros-{marca}.db'
shutil.copy2(base, respaldo)

app = create_app()
with app.app_context():
    registros_objetivo = []
    operaciones = []
    for cliente_historico, subcampania_historica, campania_id, subcampania_maestra in REGLAS:
        candidatos = AsignacionComercial.query.filter_by(
            campania_id=campania_id, subcampania=subcampania_maestra, activa=True
        ).all()
        assert candidatos, f'No existe maestro para {cliente_historico}'
        registros = Facturacion2026.query.filter_by(
            cliente=cliente_historico, subcampania=subcampania_historica
        ).all()
        for registro in registros:
            # En maestros duplicados por jefe se respeta el jefe ya informado.
            maestro = next((a for a in candidatos if a.jefe_site == registro.jefe_site), candidatos[0])
            registro.cliente, registro.gerente = maestro.cliente, maestro.gerente
            registro.jefe_site, registro.campania = maestro.jefe_site, maestro.campania
            registro.subcampania, registro.tipo_negocio = maestro.subcampania, maestro.tipo_negocio
        registros_objetivo.extend(registros)
        operaciones.append(f'{cliente_historico}: {len(registros)}')

    ids = [r.id for r in registros_objetivo]
    antes = {campo: round(sum(float(getattr(r, campo) or 0) for r in registros_objetivo), 4)
             for campo in NUMERICOS}
    db.session.flush()
    despues_registros = Facturacion2026.query.filter(Facturacion2026.id.in_(ids)).all()
    despues = {campo: round(sum(float(getattr(r, campo) or 0) for r in despues_registros), 4)
               for campo in NUMERICOS}
    assert antes == despues, f'Control numérico falló: {antes} != {despues}'
    db.session.add(HistorialCambio(
        accion='edicion', entidad='facturacion', entidad_id='alineacion-datos-maestros',
        resumen=f'Alineación general con Datos Maestros: {len(ids)} registros',
        detalle=f'{"; ".join(operaciones)}. Valores numéricos sin cambios. Respaldo: {respaldo.name}',
        antes=str(antes), despues=str(despues),
    ))
    db.session.commit()
print(f'Alineación OK: {len(ids)} registros; valores numéricos intactos. Respaldo: {respaldo}')
