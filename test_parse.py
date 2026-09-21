"""Tests del parser. Correr:  ./venv/bin/python -m pytest -q   (o: python test_parse.py)"""
import datetime as dt

from sync import parse_schedule

HOY = dt.date(2026, 9, 7)


def test_formato_iso_basico():
    s = parse_schedule(
        "2026-09-08 09:30 | Congregacional | T-24 | Uruguay y Santa Teresita | Emanuel",
        hoy=HOY,
    )[0]
    assert s.fecha == dt.date(2026, 9, 8)
    assert s.hora == dt.time(9, 30)
    assert s.salida == "Congregacional"
    assert s.punto == "Uruguay y Santa Teresita"
    assert s.conductor == "Emanuel"
    assert s.duracion_min == 120
    assert s.resumen() == "Predicacion 09:30 - Congregacional"


def test_fecha_en_espaniol_sin_anio_toma_el_mas_cercano():
    s = parse_schedule("08-sept 17:00 | Congregacional | T-22 | Jose Ares | Leonel", hoy=HOY)[0]
    assert s.fecha == dt.date(2026, 9, 8)


def test_fecha_pasada_sin_anio_salta_al_anio_siguiente():
    s = parse_schedule("02-ene 09:30 | Congregacional | T-1 | Salon | Juan", hoy=HOY)[0]
    assert s.fecha == dt.date(2027, 1, 2)


def test_hora_en_campo_separado_y_tabs():
    s = parse_schedule("2026-09-12\t09:30\tGrupo 1\tT-14\tCasa Perez\tPedro", hoy=HOY)[0]
    assert s.hora == dt.time(9, 30)
    assert s.salida == "Grupo 1"


def test_punto_a_confirmar_queda_vacio():
    s = parse_schedule(
        "2026-09-12 09:30 | Grupo La Colonia | Colonia Sur | -- A confirmar -- | Leandro",
        hoy=HOY,
    )[0]
    assert s.punto == ""


def test_duracion_explicita_y_orden():
    txt = (
        "# comentario\n"
        "2026-09-09 17:00 | Congregacional | T-9 | 25 de Mayo | Daniel | 90\n"
        "\n"
        "2026-09-09 09:30 | Congregacional | T-25 | Uruguay | Emilio\n"
    )
    salidas = parse_schedule(txt, hoy=HOY)
    assert [s.hora.hour for s in salidas] == [9, 17]
    assert salidas[1].duracion_min == 90
    assert salidas[1].fin == dt.datetime(2026, 9, 9, 18, 30)


def test_linea_incompleta_falla():
    try:
        parse_schedule("2026-09-08 09:30 | Congregacional | T-24", hoy=HOY)
    except ValueError:
        return
    raise AssertionError("deberia fallar por faltar campos")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests ok")
