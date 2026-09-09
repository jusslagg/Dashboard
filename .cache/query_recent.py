import sqlite3, json
c = sqlite3.connect('instance/facturacion.db')
c.row_factory = sqlite3.Row
fields = ('id','fecha','mes','cliente','gerente','jefe_site','campania','subcampania','tipo_jornada','horas_objetivo','horas_facturadas','horas_penalizadas','valor_hora_objetivo','valor_hora','creado_en','actualizado_en')
rows = c.execute('select * from facturacion_anio where id >= 1400 order by id').fetchall()
print(json.dumps([{k:r[k] for k in fields if k in r.keys()} for r in rows], ensure_ascii=False, indent=2, default=str))
print('HISTORY COLS', [dict(x) for x in c.execute('pragma table_info(historial_cambios)')])
print('HISTORY')
hist = c.execute("select * from historial_cambios where entidad='facturacion' and cast(entidad_id as integer)>=1400 order by id").fetchall()
print(json.dumps([dict(r) for r in hist], ensure_ascii=False, indent=2, default=str))
