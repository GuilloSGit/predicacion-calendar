#!/usr/bin/env python3
"""Sincroniza el cuadro de salidas de predicacion con Google Calendar.

Uso rapido:
    python sync.py semana.txt              # sincroniza lo que haya en el archivo
    pbpaste | python sync.py               # pega desde el portapapeles (macOS)
    python sync.py semana.txt --dry-run    # muestra que haria, sin tocar el calendario

Formato de entrada (una salida por linea, campos separados por "|"):

    2026-09-08 09:30 | Congregacional | Comenzar T-24 | Uruguay entrada Barrio Santa Teresita | Juan Pérez

Campos:  fecha+hora | salida | territorios | punto de encuentro | conductor | [duracion_min]

- Las lineas vacias y las que empiezan con "#" se ignoran.
- La fecha acepta "2026-09-08" o "08-sept" (si no pones anio, se asume el mas cercano).
- La hora acepta "9:30", "09:30", "17:00".
- El ultimo campo (duracion en minutos) es opcional; por defecto 120.
- Tambien se aceptan campos separados por TAB (por si pegas desde una planilla).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from dataclasses import dataclass, field

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_CALENDAR_NAME = "Predicacion - Congre Media Agua"
DEFAULT_TZ = "America/Argentina/San_Juan"
DEFAULT_DURATION_MIN = 120
DEFAULT_REMINDER_MIN = 30
SYNC_TAG_KEY = "predicacionSync"
SYNC_TAG_VALUE = "1"

MESES = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9,
    "septiembre": 9, "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}

DATE_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
DATE_ES_RE = re.compile(r"^(\d{1,2})[-/ ]([A-Za-zaeiouAEIOUáéíóú]+)\.?(?:[-/ ](\d{4}))?$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


@dataclass
class Salida:
    fecha: dt.date
    hora: dt.time
    salida: str
    territorios: str
    punto: str
    conductor: str
    duracion_min: int = DEFAULT_DURATION_MIN

    @property
    def inicio(self) -> dt.datetime:
        return dt.datetime.combine(self.fecha, self.hora)

    @property
    def fin(self) -> dt.datetime:
        return self.inicio + dt.timedelta(minutes=self.duracion_min)

    @property
    def slot(self) -> str:
        return f"{self.fecha.isoformat()}T{self.hora.strftime('%H:%M')}"

    def resumen(self) -> str:
        return f"Predicacion {self.hora.strftime('%H:%M')} - {self.salida}".strip(" -")

    def descripcion(self) -> str:
        lineas = [
            f"Salida: {self.salida}",
            f"Territorios: {self.territorios}",
            f"Punto de encuentro: {self.punto}",
            f"Conductor: {self.conductor}",
            "",
            "Generado por predicacion-calendar",
        ]
        return "\n".join(l for l in lineas if l is not None)


def _parse_fecha(token: str, hoy: dt.date) -> dt.date:
    token = token.strip()
    m = DATE_ISO_RE.match(token)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = DATE_ES_RE.match(token)
    if m:
        dia = int(m.group(1))
        mes_txt = m.group(2).lower()
        mes_txt = (mes_txt.replace("á", "a").replace("é", "e")
                   .replace("í", "i").replace("ó", "o").replace("ú", "u"))
        if mes_txt not in MESES:
            raise ValueError(f"mes desconocido: {m.group(2)!r}")
        mes = MESES[mes_txt]
        anio = int(m.group(3)) if m.group(3) else hoy.year
        fecha = dt.date(anio, mes, dia)
        if m.group(3) is None and (fecha - hoy).days < -183:
            fecha = dt.date(anio + 1, mes, dia)
        return fecha
    raise ValueError(f"fecha no reconocida: {token!r}")


def _parse_hora(token: str) -> dt.time:
    m = TIME_RE.match(token.strip())
    if not m:
        raise ValueError(f"hora no reconocida: {token!r}")
    return dt.time(int(m.group(1)), int(m.group(2)))


def _split_fields(linea: str) -> list[str]:
    if "|" in linea:
        partes = linea.split("|")
    elif "\t" in linea:
        partes = linea.split("\t")
    else:
        partes = [linea]
    return [p.strip() for p in partes]


def parse_schedule(texto: str, hoy: dt.date | None = None,
                   duracion_default: int = DEFAULT_DURATION_MIN) -> list[Salida]:
    hoy = hoy or dt.date.today()
    salidas: list[Salida] = []
    for nro, cruda in enumerate(texto.splitlines(), start=1):
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        partes = _split_fields(linea)
        if len(partes) < 5:
            raise ValueError(
                f"linea {nro}: se esperaban al menos 5 campos separados por '|', "
                f"hay {len(partes)}: {cruda!r}"
            )

        # El primer campo trae fecha y (casi siempre) hora juntas.
        tokens = partes[0].split()
        fecha_tok = tokens[0] if tokens else ""
        hora_tok = None
        for t in tokens[1:]:
            if TIME_RE.match(t):
                hora_tok = t
                break

        resto = partes[1:]
        if hora_tok is None:
            # La hora esta en el segundo campo.
            if resto and TIME_RE.match(resto[0]):
                hora_tok = resto[0]
                resto = resto[1:]
            else:
                raise ValueError(f"linea {nro}: no encuentro la hora: {cruda!r}")

        if len(resto) < 4:
            raise ValueError(
                f"linea {nro}: faltan campos (salida/territorios/punto/conductor): {cruda!r}"
            )

        salida, territorios, punto, conductor = resto[0], resto[1], resto[2], resto[3]
        duracion = duracion_default
        if len(resto) >= 5 and resto[4]:
            try:
                duracion = int(resto[4])
            except ValueError:
                raise ValueError(f"linea {nro}: duracion invalida: {resto[4]!r}")

        try:
            fecha = _parse_fecha(fecha_tok, hoy)
            hora = _parse_hora(hora_tok)
        except ValueError as e:
            raise ValueError(f"linea {nro}: {e}") from None

        if punto in {"--", "-- A confirmar --", "A confirmar", "-"}:
            punto = ""

        salidas.append(Salida(fecha, hora, salida, territorios, punto, conductor, duracion))

    salidas.sort(key=lambda s: s.inicio)
    return salidas


# --------------------------------------------------------------------------- #
# Google Calendar
# --------------------------------------------------------------------------- #
def get_service(credentials_path: str, token_path: str):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Token vencido o revocado: reautorizar desde cero.
                creds = None
        if not creds or not creds.valid:
            if not os.path.exists(credentials_path):
                sys.exit(
                    f"No encuentro {credentials_path}. Descarga el OAuth client "
                    "('Aplicacion de escritorio') desde Google Cloud Console y "
                    "guardalo con ese nombre. Ver README.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as fh:
            fh.write(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def ensure_calendar(service, nombre: str, tz: str) -> str:
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for item in resp.get("items", []):
            if item.get("summary") == nombre:
                return item["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    creado = service.calendars().insert(body={"summary": nombre, "timeZone": tz}).execute()
    print(f"Calendario '{nombre}' creado.")
    return creado["id"]


def _evento_body(s: Salida, tz: str, reminder_min: int) -> dict:
    return {
        "summary": s.resumen(),
        "description": s.descripcion(),
        "location": s.punto,
        "start": {"dateTime": s.inicio.isoformat(), "timeZone": tz},
        "end": {"dateTime": s.fin.isoformat(), "timeZone": tz},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": reminder_min}],
        },
        "extendedProperties": {"private": {SYNC_TAG_KEY: SYNC_TAG_VALUE, "slot": s.slot}},
    }


def sync(service, calendar_id: str, salidas: list[Salida], tz: str,
         reminder_min: int, dry_run: bool) -> None:
    if not salidas:
        print("No hay salidas para sincronizar.")
        return

    dmin = min(s.fecha for s in salidas)
    dmax = max(s.fecha for s in salidas)
    time_min = dt.datetime.combine(dmin, dt.time.min).isoformat() + "Z"
    time_max = (dt.datetime.combine(dmax, dt.time.min) + dt.timedelta(days=1)).isoformat() + "Z"

    previos = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            privateExtendedProperty=f"{SYNC_TAG_KEY}={SYNC_TAG_VALUE}",
            singleEvents=True, pageToken=page_token,
        ).execute()
        previos.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"Rango {dmin} -> {dmax}: {len(previos)} evento(s) previos de este sync, "
          f"{len(salidas)} salida(s) nuevas.")

    if dry_run:
        for s in salidas:
            print(f"  + {s.slot}  {s.resumen()}  @ {s.punto or '(sin lugar)'}")
        if previos:
            print(f"  (se borrarian {len(previos)} evento(s) previos en el rango)")
        return

    for ev in previos:
        service.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
    if previos:
        print(f"Borrados {len(previos)} evento(s) previos.")

    for s in salidas:
        service.events().insert(
            calendarId=calendar_id, body=_evento_body(s, tz, reminder_min)
        ).execute()
        print(f"  creado: {s.slot}  {s.resumen()}")


def main() -> None:
    p = argparse.ArgumentParser(description="Sincroniza salidas de predicacion con Google Calendar.")
    p.add_argument("archivo", nargs="?", help="archivo con el cuadro; si se omite, lee de stdin")
    p.add_argument("--dry-run", action="store_true", help="muestra sin tocar el calendario")
    p.add_argument("--calendar-name", default=DEFAULT_CALENDAR_NAME)
    p.add_argument("--tz", default=DEFAULT_TZ)
    p.add_argument("--duration", type=int, default=DEFAULT_DURATION_MIN,
                   help="duracion por defecto en minutos (si la linea no la trae)")
    p.add_argument("--reminder", type=int, default=DEFAULT_REMINDER_MIN,
                   help="minutos de aviso antes de cada salida")
    p.add_argument("--credentials", default="credentials.json")
    p.add_argument("--token", default="token.json")
    args = p.parse_args()

    if args.archivo:
        with open(args.archivo, encoding="utf-8") as fh:
            texto = fh.read()
    else:
        if sys.stdin.isatty():
            print("Pega el cuadro y termina con Ctrl-D:", file=sys.stderr)
        texto = sys.stdin.read()

    try:
        salidas = parse_schedule(texto, duracion_default=args.duration)
    except ValueError as e:
        sys.exit(f"Error al leer el cuadro: {e}")

    if not salidas:
        sys.exit("No se encontro ninguna salida en la entrada.")

    print(f"Leidas {len(salidas)} salida(s):")
    for s in salidas:
        print(f"  {s.fecha} {s.hora.strftime('%H:%M')}  {s.salida} / {s.territorios} "
              f"/ {s.punto or '(sin lugar)'} / {s.conductor}")
    print()

    if args.dry_run and not os.path.exists(args.token) and not os.path.exists(args.credentials):
        print("(dry-run sin credenciales: solo se valido el parseo)")
        return

    service = get_service(args.credentials, args.token)
    calendar_id = ensure_calendar(service, args.calendar_name, args.tz)
    sync(service, calendar_id, salidas, args.tz, args.reminder, args.dry_run)
    print("\nListo.")


if __name__ == "__main__":
    main()
