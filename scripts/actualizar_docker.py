"""Actualiza el Docker local desde una rama publicada en el remoto."""
import argparse
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.cache' / 'docker-auto'


def run(args, *, cwd=ROOT, env=None, timeout=600):
    result = subprocess.run(
        [str(a) for a in args], cwd=cwd, env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    if result.returncode:
        raise RuntimeError(f'{args[0]} {args[1]}: {result.stderr[-3000:]}')
    return result.stdout.strip()


def docker_path():
    found = shutil.which('docker')
    if found:
        return found
    for folder in [
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin',
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Docker/Docker/resources/bin',
    ]:
        if (folder / 'docker.exe').exists():
            return str(folder / 'docker.exe')
    raise RuntimeError('Docker no está instalado.')


def update(force=False):
    config = json.loads((STATE / 'config.json').read_text('utf-8'))
    docker = docker_path()
    env = os.environ.copy()
    env['PATH'] = str(Path(docker).parent) + os.pathsep + env.get('PATH', '')
    env['GIT_TERMINAL_PROMPT'] = '0'
    run([docker, 'info', '--format', '{{.ServerVersion}}'], env=env, timeout=30)
    repo = STATE / 'repo'
    if not (repo / 'HEAD').exists():
        run(['git', 'init', '--bare', repo])
    run(['git', '-C', repo, 'fetch', '--depth=1', config['remote'], config['branch']], env=env, timeout=120)
    commit = run(['git', '-C', repo, 'rev-parse', 'FETCH_HEAD'])
    record = STATE / 'estado.json'
    previous = json.loads(record.read_text('utf-8')) if record.exists() else {}
    if commit == previous.get('commit') and not force:
        logging.info('Sin cambios en %s', config['branch'])
        return
    image = 'dashboard-facturacion:auto-' + commit
    logging.info('Construyendo %s desde %s', image, config['branch'])
    with tempfile.TemporaryDirectory(prefix='build-', dir=STATE) as folder:
        source = Path(folder)
        archive = source / 'source.tar'
        run(['git', '-C', repo, 'archive', '--format=tar', '--output', archive, commit])
        # El archivo proviene del remoto configurado, la extracción queda dentro
        # del directorio temporal de esta compilación.
        import tarfile
        with tarfile.open(archive) as stream:
            stream.extractall(source, filter='data')
        archive.unlink()
        run([docker, 'build', '--label', 'org.opencontainers.image.revision=' + commit,
             '--tag', image, '.'], cwd=source, env=env, timeout=1200)
    candidate = 'dashboard-auto-check-' + commit[:12]
    smoke_env = {**env, 'SECRET_KEY': secrets.token_urlsafe(48)}
    try:
        run([docker, 'run', '-d', '--name', candidate, '--env', 'SECRET_KEY',
             '--health-interval=2s', '--health-start-period=5s', image], env=smoke_env)
        for _ in range(40):
            health = run([docker, 'inspect', '--format', '{{.State.Health.Status}}', candidate], env=env)
            if health == 'healthy':
                break
            time.sleep(2)
        else:
            raise RuntimeError('La imagen nueva no pasó el healthcheck.')
    finally:
        run([docker, 'rm', '-f', '-v', candidate], env=env)
    deploy_env = {**env, 'DASHBOARD_IMAGE': image}
    compose = [docker, 'compose', '--project-name', 'dashboard-facturacion',
               '--file', ROOT / 'compose.yaml', '--env-file', ROOT / '.env.docker']
    current = run([*compose, 'ps', '-q', 'web'], env=env)
    if current:
        backups = STATE / 'backups'
        backups.mkdir(exist_ok=True)
        backup = backups / f'{time.time_ns()}-{commit[:12]}.db'
        run([docker, 'exec', current, 'python', '-c',
             "import os,sqlite3; from urllib.parse import urlparse; "
             "url=os.environ['DATABASE_URL']; "
             "assert url.startswith('sqlite:///'), 'El respaldo PostgreSQL requiere la herramienta del servidor'; "
             "source=sqlite3.connect(url[10:]); "
             "target=sqlite3.connect('/tmp/dashboard-auto-backup.db'); "
             "source.backup(target); target.close(); source.close()"], env=env)
        run([docker, 'cp', current + ':/tmp/dashboard-auto-backup.db', backup], env=env)
    run([*compose, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '120', 'web'],
        env=deploy_env, timeout=180)
    settings = ROOT / '.env.docker'
    lines = settings.read_text('utf-8').splitlines()
    lines = [line for line in lines if not line.startswith('DASHBOARD_IMAGE=')]
    lines.append('DASHBOARD_IMAGE=' + image)
    temporary = settings.with_suffix('.docker.tmp')
    temporary.write_text('\n'.join(lines) + '\n', 'utf-8')
    temporary.replace(settings)
    record.write_text(json.dumps({'commit': commit, 'image': image, 'branch': config['branch']}, indent=2), 'utf-8')
    logging.info('Actualizado y healthy: %s', commit)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=STATE / 'actualizaciones.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    with (STATE / 'ejecucion.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return
        try:
            update(args.force)
        except Exception:
            logging.exception('No se pudo completar la actualización')
            raise


if __name__ == '__main__':
    main()
