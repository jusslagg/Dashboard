"""Check the real login route without importing Flask or running schema changes."""
import os
import sys
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener


def main():
    port = int(os.getenv('PORT', '8009'))
    request = Request(f'http://127.0.0.1:{port}/login')
    try:
        # Corporate proxy settings must not redirect a container-local probe.
        with build_opener(ProxyHandler({})).open(request, timeout=8) as response:
            if response.status == 200 and b'tituloLogin' in response.read():
                return 0
    except (OSError, URLError):
        pass
    print('Dashboard login is not ready.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
