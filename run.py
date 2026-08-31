# filepath: run.py
from app import create_app
import os
from werkzeug.serving import WSGIRequestHandler


class AppRequestHandler(WSGIRequestHandler):
    """Evita divulgar versiones del runtime en el servidor local."""
    server_version = 'CAT'
    sys_version = ''

app = create_app()

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '8009'))
    if os.getenv('USE_DEV_SERVER', '0') == '1':
        app.run(
            debug=os.getenv('FLASK_DEBUG', '0') == '1', host=host, port=port,
            use_reloader=os.getenv('FLASK_RELOAD', '0') == '1', request_handler=AppRequestHandler,
        )
    else:
        from waitress import serve
        serve(app, host=host, port=port, ident='CAT', threads=8)
