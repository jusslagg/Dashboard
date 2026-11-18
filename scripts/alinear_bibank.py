"""Unifica la grafía BIBANK en el maestro y sus datos relacionados."""
import argparse
import json
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import DashboardOperativo, HistorialCambio, MODELOS_CON_IDENTIDAD_COMERCIAL, _clave_nombre
from sqlalchemy import Numeric, Integer, Float


def coincide(valor):
    return _clave_nombre(str(valor or '')) == 'bibank'


def normalizar_json(valor):
    if isinstance(valor, str):
        return 'BIBANK' if coincide(valor) else valor
    if isinstance(valor, list):
        return [normalizar_json(item) for item in valor]
    if isinstance(valor, dict):
        return {clave: normalizar_json(item) for clave, item in valor.items()}
    return valor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        db.session.info['normalizando_nombres_comerciales'] = True
        cambios, cantidades = [], Counter()
        for modelo in MODELOS_CON_IDENTIDAD_COMERCIAL:
            for registro in modelo.query.all():
                campos = [campo for campo in ('cliente', 'nombre', 'campania', 'subcampania',
                                               'cliente_destino', 'campania_destino')
                          if hasattr(registro, campo) and coincide(getattr(registro, campo))]
                if not campos:
                    continue
                numericos = {col.key: getattr(registro, col.key) for col in modelo.__table__.columns
                             if isinstance(col.type, (Numeric, Integer, Float))}
                antes = {campo: getattr(registro, campo) for campo in campos}
                for campo in campos:
                    setattr(registro, campo, 'BIBANK')
                if isinstance(registro, DashboardOperativo) and registro.datos:
                    original = json.loads(registro.datos)
                    normalizado = normalizar_json(original)
                    if normalizado != original:
                        registro.datos = json.dumps(normalizado, ensure_ascii=False)
                assert numericos == {campo: getattr(registro, campo) for campo in numericos}
                if any(valor != 'BIBANK' for valor in antes.values()):
                    cambios.append({'tabla': modelo.__tablename__, 'id': registro.id, 'antes': antes})
                    cantidades[modelo.__tablename__] += 1
        db.session.flush()
        resumen = {'grafia': 'BIBANK', 'registros_actualizados': len(cambios), 'tablas': dict(cantidades)}
        if args.apply:
            db.session.add(HistorialCambio(accion='edicion', entidad='identidad_comercial', entidad_id='BIBANK',
                resumen=f'Grafía BIBANK en {len(cambios)} registros',
                antes=json.dumps({'cambios': cambios}, ensure_ascii=False),
                despues=json.dumps(resumen, ensure_ascii=False)))
            db.session.commit()
        else:
            db.session.rollback()
        db.session.info.pop('normalizando_nombres_comerciales', None)
        print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
