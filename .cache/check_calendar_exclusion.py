import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
app=create_app()
with app.test_client() as client:
    with client.session_transaction() as session: session['usuario_id']=1
    rows=client.get('/api/notificaciones-proyecciones?year=2026&mes=2026-02').get_json()['notificaciones']
    matches=[row for row in rows if row['cliente']=='Assurant' and row['campania']=='Assurant']
    print(matches)
    assert not matches, 'Assurant enero/febrero solo cambia por calendario y no debe notificarse'
    print('calendar-effect-excluded')
