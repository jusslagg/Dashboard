"""Sincroniza las fuentes de Proyectados desde el libro operativo 2026."""

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import (
    NextGenDolar,
    NextGenProducto,
    ProyeccionMatriz,
    ProyeccionMatrizJornada,
    ProyeccionPrecio,
    TarifacionCampania,
    VariableCampania,
)
from app.routes import normalizar_header, registrar_historial, snapshot_proyeccion


YEAR = 2026


def mes(valor):
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m")
    if hasattr(valor, "year") and hasattr(valor, "month"):
        return f"{valor.year:04d}-{valor.month:02d}"
    return None


def numero(valor, default=0):
    if valor in (None, ""):
        return default
    return float(valor)


def texto(valor):
    return str(valor or "").strip()


def snapshot_simple(registro, tipo=None):
    if not registro:
        return None
    data = registro.to_dict()
    if tipo:
        data["tipo_registro"] = tipo
    return data


def guardar_historial(entidad, clave, resumen, antes, despues):
    claves = {"proyeccion_matriz": "proyecciones", "matriz_precios": "precios"}
    contenedor = claves.get(entidad, entidad)
    registrar_historial(
        "importacion",
        entidad,
        clave,
        resumen,
        antes={contenedor: antes},
        despues={contenedor: despues},
    )


def sincronizar_matriz(workbook):
    sheet = workbook["Matriz"]
    grupos = defaultdict(list)
    for row in sheet.iter_rows(min_row=3, values_only=True):
        cliente, campania, year, fecha = texto(row[2]), texto(row[3]), row[4], row[5]
        clave_mes = mes(fecha)
        # El período de la fila manda sobre la columna Año. El libro incluye,
        # por ejemplo, una jornada de mayo-2026 rotulada accidentalmente 2027
        # y sus propias fórmulas la incorporan al total de mayo.
        if not cliente or not campania or not clave_mes or not clave_mes.startswith(str(YEAR)):
            continue
        grupos[(cliente, campania, clave_mes)].append(row)

    existentes = {(r.cliente, r.campania, r.mes): r for r in ProyeccionMatriz.query.filter_by(year=YEAR).all()}
    # La hoja Matriz no reemplaza las aperturas PLP mantenidas por la app.
    # Se actualizan las claves presentes en el libro y se preservan las demás.
    claves = sorted(set(grupos))
    antes, despues = [], []
    for clave in claves:
        registro = existentes.get(clave)
        antes.append(snapshot_proyeccion(registro))
        filas = grupos.get(clave)
        if not registro:
            registro = ProyeccionMatriz(cliente=clave[0], campania=clave[1], year=YEAR, mes=clave[2])
            db.session.add(registro)
        total_dotacion = sum(numero(f[9]) for f in filas)
        total_requeridas = sum(numero(f[10]) for f in filas)
        total_proyectadas = sum(numero(f[11]) for f in filas)
        registro.cliente, registro.campania, registro.year, registro.mes = clave[0], clave[1], YEAR, clave[2]
        registro.dotacion_requerida = total_dotacion
        registro.carga_semanal = texto(filas[0][6]) or "L a V"
        registro.carga_horaria = sum(numero(f[8]) * numero(f[9]) for f in filas) / total_dotacion if total_dotacion else 0
        registro.dias_objetivo = int(max(numero(f[7]) for f in filas))
        registro.horas_requeridas = total_requeridas
        registro.porcentaje_cumplimiento = total_proyectadas / total_requeridas * 100 if total_requeridas else 100
        porcentajes_nocturnidad = [numero(f[15]) for f in filas if f[15] not in (None, "")]
        registro.tiene_nocturnidad = bool(porcentajes_nocturnidad and max(porcentajes_nocturnidad) > 0)
        registro.porcentaje_nocturnidad = max(porcentajes_nocturnidad, default=0) * 100
        registro.horas_carga_manual = True
        registro.dias_objetivo_manual = registro.dias_objetivo
        registro.horas_requeridas_manual = total_requeridas
        registro.jornadas.clear()
        for fila in filas:
            registro.jornadas.append(ProyeccionMatrizJornada(
                dotacion_requerida=numero(fila[9]), carga_semanal=texto(fila[6]) or "L a V",
                carga_horaria=numero(fila[8]), dias_objetivo=int(numero(fila[7])),
                horas_requeridas=numero(fila[10]),
            ))
        db.session.flush()
        despues.append(snapshot_proyeccion(registro))
    guardar_historial("proyeccion_matriz", str(YEAR), f"Actualización integral Matriz {YEAR}: {len(grupos)} registros", antes, despues)
    return len(grupos)


def datos_tabla_mensual(sheet, fila_inicio=5):
    headers = list(next(sheet.iter_rows(min_row=4, max_row=4, values_only=True)))
    columnas = [(i, mes(v)) for i, v in enumerate(headers) if mes(v)]
    for row in sheet.iter_rows(min_row=fila_inicio, values_only=True):
        cuenta, site, campania = texto(row[2]), texto(row[3]), texto(row[4])
        if not cuenta or not campania:
            continue
        yield cuenta, site, campania, row, columnas


def sincronizar_precios_y_fijos(workbook):
    deseados = {}
    for cliente, site, campania, row, columnas in datos_tabla_mensual(workbook["Precios"]):
        for index, clave_mes in columnas:
            if clave_mes.startswith(str(YEAR)) and row[index] not in (None, ""):
                deseados[(cliente, campania, clave_mes)] = {"site": site, "precio": numero(row[index]), "fijo": 0}

    precios_por_nombre = defaultdict(list)
    for clave in deseados:
        precios_por_nombre[normalizar_header(clave[0])].append(clave)
        precios_por_nombre[normalizar_header(clave[1])].append(clave)
    fija = workbook["Suma fija"]
    encabezados = list(next(fija.iter_rows(min_row=2, max_row=2, values_only=True)))
    # El segundo bloque mensual es el importe total por dotación que utiliza la app.
    columnas_fijas = [(i, mes(v)) for i, v in enumerate(encabezados) if i >= 14 and mes(v)]
    for row in fija.iter_rows(min_row=3, values_only=True):
        nombre = normalizar_header(row[0])
        for clave in precios_por_nombre.get(nombre, []):
            indice = next((i for i, m in columnas_fijas if m == clave[2]), None)
            if indice is not None and row[indice] not in (None, ""):
                deseados[clave]["fijo"] = numero(row[indice])

    existentes = {(r.cliente, r.campania, r.mes): r for r in ProyeccionPrecio.query.filter_by(year=YEAR).all()}
    claves = sorted(set(existentes) | set(deseados))
    antes, despues = [], []
    for clave in claves:
        registro = existentes.get(clave)
        antes.append(snapshot_simple(registro))
        data = deseados.get(clave)
        if not data:
            db.session.delete(registro); despues.append(None); continue
        if not registro:
            registro = ProyeccionPrecio(cliente=clave[0], campania=clave[1], year=YEAR, mes=clave[2])
            db.session.add(registro)
        registro.site, registro.precio_base = data["site"], Decimal(str(data["precio"]))
        registro.alcance_porcentaje, registro.importe_fijo_mensual = 100, Decimal(str(data["fijo"]))
        registro.recalcular(); db.session.flush(); despues.append(snapshot_simple(registro))
    guardar_historial("matriz_precios", str(YEAR), f"Actualización integral Precios y suma fija {YEAR}: {len(deseados)} registros", antes, despues)
    return len(deseados)


def sincronizar_variables(workbook):
    deseados = {}
    for cliente, site, campania, row, columnas in datos_tabla_mensual(workbook["Estimacion Variable"]):
        for index, clave_mes in columnas:
            if clave_mes.startswith(str(YEAR)) and row[index] not in (None, ""):
                valor = numero(row[index]); valor = valor * 100 if abs(valor) <= 1 else valor
                deseados[(cliente, campania, clave_mes)] = (site, valor)
    existentes = {(r.cliente, r.campania, r.mes): r for r in VariableCampania.query.filter_by(year=YEAR).all()}
    claves = sorted(set(existentes) | set(deseados)); antes, despues = [], []
    for clave in claves:
        registro = existentes.get(clave); antes.append(snapshot_simple(registro)); data = deseados.get(clave)
        if not data: db.session.delete(registro); despues.append(None); continue
        if not registro:
            registro = VariableCampania(cliente=clave[0], campania=clave[1], year=YEAR, mes=clave[2]); db.session.add(registro)
        registro.site, registro.porcentaje = data; db.session.flush(); despues.append(snapshot_simple(registro))
    guardar_historial("variables", str(YEAR), f"Actualización integral Variables {YEAR}: {len(deseados)} registros", antes, despues)
    return len(deseados)


def sincronizar_tarifacion(workbook):
    deseados = {}
    for cliente, site, campania, row, columnas in datos_tabla_mensual(workbook["Tarifacion"]):
        concepto = texto(row[5]) or "Tarifación"
        for index, clave_mes in columnas:
            if clave_mes.startswith(str(YEAR)) and row[index] not in (None, ""):
                deseados[(cliente, campania, concepto, clave_mes)] = (site, numero(row[index]))
    existentes = {(r.cliente, r.campania, r.concepto, r.mes): r for r in TarifacionCampania.query.filter_by(year=YEAR).all()}
    claves = sorted(set(existentes) | set(deseados)); antes, despues = [], []
    for clave in claves:
        registro = existentes.get(clave); antes.append(snapshot_simple(registro)); data = deseados.get(clave)
        if not data: db.session.delete(registro); despues.append(None); continue
        if not registro:
            registro = TarifacionCampania(cliente=clave[0], campania=clave[1], concepto=clave[2], year=YEAR, mes=clave[3]); db.session.add(registro)
        registro.site, registro.monto = data; db.session.flush(); despues.append(snapshot_simple(registro))
    guardar_historial("tarifaciones", str(YEAR), f"Actualización integral Tarifación {YEAR}: {len(deseados)} registros", antes, despues)
    return len(deseados)


def sincronizar_next_gen(workbook):
    sheet = workbook["Valores Next Gen"]
    headers = list(next(sheet.iter_rows(min_row=4, max_row=4, values_only=True)))
    columnas = [(i, mes(v)) for i, v in enumerate(headers) if mes(v)]
    dolar = list(next(sheet.iter_rows(min_row=1, max_row=1, values_only=True)))
    productos_crudos = {}
    for row in sheet.iter_rows(min_row=5, values_only=True):
        campania, producto = texto(row[3]), texto(row[4])
        if not producto: continue
        cliente = campania or producto
        for index, clave_mes in columnas:
            if row[index] not in (None, ""):
                productos_crudos[(cliente, campania or cliente, producto, clave_mes)] = numero(row[index])
    existentes_p = {(r.cliente, r.campania, r.producto, r.mes): r for r in NextGenProducto.query.filter_by(year=YEAR).all()}
    existentes_por_producto = {
        (normalizar_header(r.producto), r.mes): (r.cliente, r.campania, r.producto, r.mes)
        for r in existentes_p.values()
    }
    productos = {}
    for clave, valor in productos_crudos.items():
        clave_existente = existentes_por_producto.get((normalizar_header(clave[2]), clave[3]))
        productos[clave_existente or clave] = valor
    existentes_d = {r.mes: r for r in NextGenDolar.query.filter_by(year=YEAR).all()}
    antes, despues = [], []
    for clave_mes in [f"{YEAR}-{m:02d}" for m in range(1, 13)]:
        index = next((i for i, m in columnas if m == clave_mes), None); registro = existentes_d.get(clave_mes)
        antes.append(snapshot_simple(registro, "dolar")); valor = dolar[index] if index is not None else None
        if valor in (None, ""):
            if registro: db.session.delete(registro)
            despues.append(None); continue
        if not registro: registro = NextGenDolar(year=YEAR, mes=clave_mes); db.session.add(registro)
        registro.valor = numero(valor); db.session.flush(); despues.append(snapshot_simple(registro, "dolar"))
    for clave in sorted(set(existentes_p) | set(productos)):
        registro = existentes_p.get(clave); antes.append(snapshot_simple(registro, "producto")); valor = productos.get(clave)
        if valor is None:
            db.session.delete(registro); despues.append(None); continue
        if not registro:
            registro = NextGenProducto(cliente=clave[0], campania=clave[1], producto=clave[2], year=YEAR, mes=clave[3]); db.session.add(registro)
        registro.cantidad_usd = valor; db.session.flush(); despues.append(snapshot_simple(registro, "producto"))
    guardar_historial("next_gen", str(YEAR), f"Actualización integral Next Gen {YEAR}: {len(productos) + 12} valores", antes, despues)
    return len(productos) + 12


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archivo")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--section",
        choices=("all", "matriz", "precios", "variables", "tarifacion", "next_gen"),
        default="all",
    )
    args = parser.parse_args()
    workbook = openpyxl.load_workbook(args.archivo, data_only=True, read_only=True)
    app = create_app()
    with app.test_request_context("/sincronizacion-proyectados"):
        tareas = {
            "matriz": sincronizar_matriz,
            "precios": sincronizar_precios_y_fijos,
            "variables": sincronizar_variables,
            "tarifacion": sincronizar_tarifacion,
            "next_gen": sincronizar_next_gen,
        }
        seleccionadas = tareas.items() if args.section == "all" else [(args.section, tareas[args.section])]
        resultados = {nombre: tarea(workbook) for nombre, tarea in seleccionadas}
        if args.apply:
            db.session.commit()
        else:
            db.session.rollback()
        print(("APLICADO" if args.apply else "SIMULADO"), resultados)


if __name__ == "__main__":
    main()
