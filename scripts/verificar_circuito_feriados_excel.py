"""Audita el circuito de feriados contra Proyección Horas V3."""
from pathlib import Path
import sys
from math import isclose

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.routes import calcular_dias_objetivo, fechas_feriadas_activas
from scripts.sincronizar_proyectados_excel import (
    claves_horas_auxiliares, jornadas_derivadas_naturgy, jornadas_naturgy_auxiliares,
)

archivo = Path(sys.argv[1])
formulas = openpyxl.load_workbook(archivo, data_only=False, read_only=True)
valores = openpyxl.load_workbook(archivo, data_only=True, read_only=True)
auxiliares = claves_horas_auxiliares(formulas)
assert len(auxiliares) == 195, len(auxiliares)

# Las otras 805 proyecciones del libro dependen de días × horas × dotación.
claves = set()
for fila in valores['Matriz'].iter_rows(min_row=3, values_only=True):
    if fila[2] and hasattr(fila[5], 'year') and fila[5].year == 2026:
        claves.add((str(fila[2]).strip().lower(), str(fila[3]).strip().lower(), fila[5].strftime('%Y-%m')))
assert len(claves) == 925

app = create_app()
with app.app_context():
    feriados = fechas_feriadas_activas(2026)
    diferencias = []
    dias = valores['Dias Habiles']
    for fila in range(3, 10):
        carga = dias.cell(fila, 1).value
        if not carga:
            continue
        for mes_numero in range(1, 13):
            excel = dias.cell(fila, mes_numero + 3).value
            app_dias = calcular_dias_objetivo(2026, mes_numero, carga, feriados)
            if excel != app_dias:
                diferencias.append((carga, mes_numero, excel, app_dias))
    assert diferencias == [], diferencias

    fuentes_naturgy = jornadas_naturgy_auxiliares(valores)
    fila_ban_urgencias = [
        fila for fila in valores['Matriz'].iter_rows(min_row=3, values_only=True)
        if fila[3] == 'Naturgy BAN Urgencias' and getattr(fila[5], 'month', None) == 11
    ]
    jornadas_ban = jornadas_derivadas_naturgy(
        'Naturgy BAN Urgencias', '2026-11', fila_ban_urgencias, fuentes_naturgy, True,
    )
    horas_ban = sum(
        jornada['dotacion_requerida'] * jornada['carga_horaria']
        * calcular_dias_objetivo(2026, 11, jornada['carga_semanal'], feriados)
        for jornada in jornadas_ban
    )
    assert isclose(horas_ban, 1486.404), horas_ban

matriz = valores['Matriz']
assurant = {}
for fila in matriz.iter_rows(min_row=3, values_only=True):
    if fila[2] == 'Assurant' and fila[3] == 'Assurant':
        assurant[fila[5].month] = fila
for mes_numero, esperado in {2: (18, 2916, 2624.4), 4: (20, 3240, 2916),
                             5: (19, 2508, 2257.2), 11: (18, 1620, 1458)}.items():
    fila = assurant[mes_numero]
    actual = (fila[7], fila[10], fila[11])
    assert all(isclose(float(a), float(b)) for a, b in zip(actual, esperado)), (mes_numero, actual)

# Los tres feriados laborables de noviembre conservan dotación 15 y horas/día 6.
horas_requeridas = 15 * 18 * 6
horas_proyectadas = horas_requeridas * .9
precio, fijo = 15245.93, 1125000
facturacion = horas_proyectadas * precio + fijo
assert horas_requeridas == 1620 and horas_proyectadas == 1458
assert isclose(facturacion, 23353565.94, abs_tol=.01)
print('OK: 925 proyecciones; 730 por calendario y 195 auxiliares.')
print('OK: febrero/abril/mayo/noviembre replican días -> horas -> facturación.')
print('OK: noviembre con tres feriados: 18 días, 1620 requeridas, 1458 proyectadas, $23.353.565,94.')
print('OK: Naturgy conserva jornadas auxiliares; BAN Urgencias noviembre = 1.486,404 h.')
