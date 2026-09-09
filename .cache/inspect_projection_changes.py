import sqlite3

db = sqlite3.connect('instance/facturacion.db')
for table in ('matriz_proyecciones', 'matriz_precios', 'variables_campanias', 'tarifaciones_campanias'):
    print(table, db.execute(f"select count(*), min(mes), max(mes) from {table}").fetchone())
print('PROJ sample')
for row in db.execute("select cliente,campania,mes,dotacion_requerida,horas_requeridas,porcentaje_cumplimiento from matriz_proyecciones where year=2026 order by cliente,campania,mes limit 20"):
    print(row)
print('PRICE sample')
for row in db.execute("select cliente,campania,mes,precio_base,alcance_porcentaje,precio_final,importe_fijo_mensual from matriz_precios where year=2026 order by cliente,campania,mes limit 20"):
    print(row)
