from pathlib import Path
from zipfile import ZipFile
import re
import xml.etree.ElementTree as ET

path = Path('.cache/2026 Facturacion (37).xlsx')
ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
with ZipFile(path) as z:
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    sheets = []
    for s in wb.find('m:sheets', ns):
        target = targets[s.attrib['{'+ns['r']+'}id']].lstrip('/')
        if not target.startswith('xl/'):
            target = 'xl/' + target
        sheets.append((s.attrib['name'], target))
    print('SHEETS')
    for i, item in enumerate(sheets, 1):
        print(i, item)
    print('DEFINED NAMES')
    dn = wb.find('m:definedNames', ns)
    if dn is not None:
        for item in dn:
            print(item.attrib.get('name'), item.text)
    print('FORMULAS WITH HOUR/CUMPLIMIENTO REFERENCES')
    for name, target in sheets:
        root = ET.fromstring(z.read(target))
        hits = []
        for c in root.findall('.//m:c', ns):
            f = c.find('m:f', ns)
            if f is not None and f.text and re.search(r'hor|cumpl|requer|realiz|SUM', f.text, re.I):
                v = c.find('m:v', ns)
                hits.append((c.attrib.get('r'), f.text, v.text if v is not None else None))
        if hits:
            print('\n', name, len(hits))
            for hit in hits[:120]:
                print(hit)
