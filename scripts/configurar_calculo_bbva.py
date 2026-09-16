"""Configura la apertura del ajuste de valor hora para BBVA Seguros."""

from app import create_app, db
from app.models import ExcepcionCalculo


def configurar():
    excepcion = ExcepcionCalculo.query.filter_by(
        cliente="BBVA Seguros",
        campania="BBVA Seguros",
    ).first()
    if excepcion is None:
        excepcion = ExcepcionCalculo(
            cliente="BBVA Seguros",
            campania="BBVA Seguros",
        )
        db.session.add(excepcion)

    excepcion.tipo_calculo = "separar_ajuste_vh"
    excepcion.ajuste_vh_objetivo_pct = 0
    excepcion.ajuste_vh_alcanzado_pct = 0
    excepcion.activa = True
    db.session.commit()
    print(f"BBVA Seguros configurada (excepcion {excepcion.id}).")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        configurar()
