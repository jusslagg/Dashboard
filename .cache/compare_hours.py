from pathlib import Path
from zipfile import ZipFile
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections import Counter
from datetime import datetime, timedelta
import re

XLSX = Path('.cache/2026 Facturacion (37).xlsx')
DB = Path('instance/facturacion.db')
M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
ns = {'m': M, 'r': R, 'p': P}

def colnum(ref):
    letters = re.match(r'[A-Z]+', ref).group()
    out = 0
    for ch in letters:
        out = out * 26 + ord(ch) - 64
    return out

with ZipFile(XLSX) as z:
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall('m:si', ns):
            shared.append(''.join(t.text or '' for t in si.findall('.//m:t', ns)))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {x.attrib['Id']: x.attrib['Target'] for x in rels}
    paths = {}
    for s in wb.find('m:sheets', ns):
        target = targets[s.attrib['{'+R+'}id']].lstrip('/')
        paths[s.attrib['name']] = target if target.startswith('xl/') else 'xl/' + target

    def read_sheet(name):
        root = ET.fromstring(z.read(paths[name]))
        cells = {}
        for c in root.findall('.//m:c', ns):
            ref, typ = c.attrib['r'], c.attrib.get('t')
            formula = c.find('m:f', ns)
            val = c.find('m:v', ns)
            inline = c.find('m:is', ns)
            raw = val.text if val is not None else None
            if typ == 's' and raw is not None:
                value = shared[int(raw)]
            elif typ == 'inlineStr' and inline is not None:
                value = ''.join(t.text or '' for t in inline.findall('.//m:t', ns))
            elif typ == 'b':
                value = raw == '1'
            else:
                try: value = float(raw) if raw is not None else None
                except ValueError: value = raw
            cells[ref] = {'v': value, 'f': formula.text if formula is not None else None}
        return cells

    def cell(sheet, col, row):
        return sheet.get(f'{col}{row}', {}).get('v')

    def number(value):
        try: return float(value or 0)
        except (TypeError, ValueError): return 0.0

    reloj = read_sheet('Reloj')
    print('RELOJ CELLS')
    for ref, data in sorted(reloj.items(), key=lambda x: (int(re.search(r'\d+', x[0]).group()), colnum(x[0]))):
        if data['v'] not in (None, '') or data['f']:
            print(ref, repr(data['v']), 'FORMULA=', data['f'])

    data = read_sheet('2026')
    print('\n2026 HEADERS ROWS 1-3')
    for row in range(1, 4):
        print('ROW', row, [(ref, d['v']) for ref, d in sorted(data.items(), key=lambda x: colnum(x[0])) if int(re.search(r'\d+', ref).group()) == row])
    for col in ('A','B','C','D','E','F','G','H','I','J','K','L','M'):
        nums = [float(cell(data,col,row) or 0) for row in range(3, 2000) if isinstance(cell(data,col,row),(int,float))]
        if nums:
            print('SUM', col, sum(nums), 'COUNT', len(nums))

    # Create normalized Excel rows using the visible source table columns.
    excel_rows = []
    max_row = max(int(re.search(r'\d+', ref).group()) for ref in data)
    for row in range(3, max_row + 1):
        if any(cell(data, col, row) not in (None, '') for col in ('D','E','F','G','J','K','L')):
            excel_rows.append({
                'row': row, 'razon': cell(data,'D',row), 'cliente': cell(data,'E',row),
                'gerente': cell(data,'F',row), 'campania': cell(data,'G',row), 'sub': cell(data,'H',row),
                'tipo': cell(data,'I',row), 'mes': cell(data,'J',row),
                'obj': number(cell(data,'K',row)), 'real': number(cell(data,'L',row)),
            })
    print('\nEXCEL TOTAL', sum(x['obj'] for x in excel_rows), sum(x['real'] for x in excel_rows), 'ROWS', len(excel_rows))
    ex_group = defaultdict(lambda: [0,0,0])
    for x in excel_rows:
        key = tuple(str(x[k] or '').strip().casefold() for k in ('cliente','gerente','campania','sub','mes','tipo'))
        ex_group[key][0] += x['obj']; ex_group[key][1] += x['real']; ex_group[key][2] += 1

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cols = [x['name'] for x in con.execute('pragma table_info(facturacion_anio)')]
print('\nDB COLS', cols)
rows = con.execute("select * from facturacion_anio where substr(mes,1,4)='2026'").fetchall()
print('DB TOTAL', sum(float(x['horas_objetivo'] or 0) for x in rows), sum(float(x['horas_facturadas'] or 0) for x in rows), 'ROWS', len(rows))

def pair(obj, real):
    return (round(float(obj or 0), 6), round(float(real or 0), 6))

excel_pairs = Counter(pair(x['obj'], x['real']) for x in excel_rows if x['obj'] or x['real'])
db_pairs = Counter(pair(x['horas_objetivo'], x['horas_facturadas']) for x in rows if x['horas_objetivo'] or x['horas_facturadas'])
print('NONZERO ROWS EXCEL/DB', sum(excel_pairs.values()), sum(db_pairs.values()))
print('\nPAIR MULTISET DB EXTRA')
for values, count in (db_pairs - excel_pairs).most_common():
    matches = [dict(x) for x in rows if pair(x['horas_objetivo'], x['horas_facturadas']) == values]
    print(count, values, [{k: m[k] for k in ('id','mes','cliente','gerente','jefe_site','campania','subcampania','tipo_jornada','fecha')} for m in matches[:count+2]])
print('\nPAIR MULTISET EXCEL EXTRA')
for values, count in (excel_pairs - db_pairs).most_common():
    matches = [x for x in excel_rows if pair(x['obj'], x['real']) == values]
    print(count, values, matches[:count+2])
db_group = defaultdict(lambda: [0,0,0])
for x in rows:
    vals = {'cliente':x['cliente'], 'gerente':x['gerente'], 'campania':x['campania'], 'sub':x['subcampania'], 'mes':x['mes'], 'tipo':x['tipo_jornada']}
    key = tuple(str(vals[k] or '').strip().casefold() for k in ('cliente','gerente','campania','sub','mes','tipo'))
    db_group[key][0] += float(x['horas_objetivo'] or 0); db_group[key][1] += float(x['horas_facturadas'] or 0); db_group[key][2] += 1

diffs = []
for key in set(ex_group) | set(db_group):
    ex, db = ex_group[key], db_group[key]
    d1, d2 = db[0]-ex[0], db[1]-ex[1]
    if abs(d1) > .001 or abs(d2) > .001:
        diffs.append((abs(d1)+abs(d2), d1, d2, key, ex, db))
print('\nGROUP DIFFERENCES (DB - EXCEL)')
for _, d1, d2, key, ex, db in sorted(diffs, reverse=True)[:100]:
    print('DIFF', round(d1,6), round(d2,6), 'KEY', key, 'EX', [round(v,6) for v in ex], 'DB', [round(v,6) for v in db])
