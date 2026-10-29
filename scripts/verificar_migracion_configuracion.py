"""Check source compatibility before and after adding operational preferences."""
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.models import ConfiguracionOperativa, db
folder = ROOT / '.cache' / ('migration-settings-' + uuid4().hex)
folder.mkdir(parents=True)
source_url = 'sqlite:///' + (folder / 'source.db').as_posix()
source = create_engine(source_url)
db.metadata.create_all(source)
with source.begin() as connection:
    connection.execute(text("INSERT INTO campanias (id,cliente,nombre,activa,creado_en) VALUES (1,'Migration fixture','Campaign',1,'2026-10-28')"))
ConfiguracionOperativa.__table__.drop(source)
for label in ('legacy','current'):
    if label == 'current':
        ConfiguracionOperativa.__table__.create(source)
        with source.begin() as connection:
            connection.execute(text("INSERT INTO configuracion_operativa (clave,valor,version) VALUES ('anio_predeterminado','2030',1)"))
    target_url = 'sqlite:///' + (folder / (label + '.db')).as_posix()
    result = subprocess.run([sys.executable,'scripts/migrar_base_datos.py','--source-url',source_url,'--target-url',target_url],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    target = create_engine(target_url)
    with target.connect() as connection:
        assert connection.execute(text('SELECT COUNT(*) FROM campanias')).scalar_one() == 1
        settings = connection.execute(text('SELECT valor FROM configuracion_operativa')).scalars().all()
        assert settings == ([] if label == 'legacy' else ['2030'])
    target.dispose()
source.dispose()
print('OK: old-source migration initializes empty settings; current-source migration preserves year and verifies content parity.')
