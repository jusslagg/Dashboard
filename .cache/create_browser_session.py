import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app

app = create_app()
with app.test_client() as client:
    with client.session_transaction() as browser_session:
        browser_session["usuario_id"] = 1
    cookie = client.get_cookie(app.config.get("SESSION_COOKIE_NAME", "session"))
    Path(".cache/session-cookie.txt").write_text(cookie.value, encoding="utf-8")
