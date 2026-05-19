# filepath: run.py
from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('PORT', '8009')),
        use_reloader=os.getenv('FLASK_RELOAD', '0') == '1',
    )
