"""Build a Docker source handoff from an explicit allowlist, without local databases."""
from hashlib import sha256
from pathlib import Path
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ('Dockerfile', 'compose.yaml', '.dockerignore', '.env.docker.example',
              '.gitignore', 'requirements.txt', 'run.py', 'README.md')
SCRIPTS = ('database_contract.py', 'migrar_base_datos.py', 'docker_healthcheck.py',
           'verificar_arranque_docker.py', 'verificar_administracion.py',
           'verificar_migracion_configuracion.py', 'verificar_continuidad_anual.py',
           'verificar_alertas_dashboard.py', 'empaquetar_docker.py')


def allowed(path):
    relative = path.relative_to(ROOT)
    if path.is_symlink() or '__pycache__' in relative.parts:
        return False
    name = path.name.lower()
    if name.startswith('.env'):
        return relative.as_posix() == '.env.docker.example'
    return not (name.endswith(('.pyc', '.pyo', '.db', '.sqlite', '.sqlite3', '.log', '.pem', '.key', '.pfx'))
                or '.db-' in name)


def main():
    paths = [ROOT / name for name in ROOT_FILES]
    paths += [ROOT / 'scripts' / name for name in SCRIPTS]
    paths += [path for directory in ('app', 'config', 'docs')
              for path in (ROOT / directory).rglob('*') if path.is_file()]
    payload = {}
    for path in sorted(set(paths)):
        if allowed(path):
            payload[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    payload['LEER_PRIMERO.txt'] = (
        'ENTREGA A DESARROLLO - DASHBOARD DE FACTURACION\n\n'
        'Paquete de codigo fuente de la aplicacion Flask operativa para construir con Docker.\n'
        'No es una imagen Docker ya construida. No incluye la base local ni credenciales.\n'
        'Incluye los JSON historicos versionados que utiliza la aplicacion.\n'
        'El frontend Next.js en migracion no forma parte de esta entrega.\n\n'
        '1. Extraer el ZIP en una carpeta. Abrir docs/DOCKER.md.\n'
        '2. Con Docker iniciado, copiar .env.docker.example a .env.docker.\n'
        '3. Generar y configurar una SECRET_KEY propia y persistente.\n'
        '4. docker compose --env-file .env.docker config --quiet\n'
        '5. docker compose --env-file .env.docker build --pull\n'
        '6. Para conservar los datos actuales, importar la base ANTES del primer up;\n'
        '   seguir la seccion 3 de la guia. Para una instalacion nueva, continuar.\n'
        '7. docker compose --env-file .env.docker up -d\n'
        '8. Abrir http://127.0.0.1:8010 para la prueba local por HTTP.\n\n'
        'Empresa: configurar HTTPS, APP_ENV=production, base y secretos del servidor.\n'
        'Acordar registro de imagenes, repositorio y version con Infraestructura.\n'
        'La base y credenciales se transfieren por separado, por el canal interno autorizado.\n\n'
        'Validacion: smoke local de arranque, login HTTPS, persistencia y healthcheck aprobado.\n'
        'Pendiente: build y ejecucion real con Docker Engine; Docker no esta instalado en la PC de origen.\n'
        'MANIFIESTO_ARCHIVOS.json permite comprobar el contenido de cada archivo recibido.\n'
    ).encode('utf-8')
    manifest = {name: {'bytes':len(content), 'sha256':sha256(content).hexdigest()}
                for name, content in sorted(payload.items())}
    payload['MANIFIESTO_ARCHIVOS.json'] = json.dumps(manifest, indent=2, ensure_ascii=False).encode('utf-8')
    output = ROOT / 'entregas'
    output.mkdir(exist_ok=True)
    archive = output / 'Dashboard-Docker-Desarrollo.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, content in sorted(payload.items()):
            zipped.writestr(name,content)
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        for name, expected in manifest.items():
            assert sha256(zipped.read(name)).hexdigest() == expected['sha256'], name
        assert '.env' not in zipped.namelist()
        assert not any(name.startswith(('instance/','.git/','node_modules/','.venv/')) for name in zipped.namelist())
    digest = sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n',encoding='ascii')
    print(f'ZIP verificado: {archive}')
    print(f'{len(payload)} archivos; {archive.stat().st_size / 1024 / 1024:.2f} MB')
    print(f'SHA256: {digest}')


if __name__ == '__main__':
    main()
