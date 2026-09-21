"""Convierte una imagen del cuadro de salidas en el texto que entiende sync.py,
usando Gemini (la IA de Google).

Uso desde codigo:
    from extract import image_to_txt
    txt = image_to_txt("cuadro.png", api_key="...", anio=2026)

Uso desde consola:
    GEMINI_API_KEY=... python extract.py cuadro.png > semana.txt
"""
from __future__ import annotations

import datetime as dt
import logging
import mimetypes
import os
import sys
import time

# Modelo preferido primero; si no esta disponible se prueba el siguiente.
MODELOS = [m.strip() for m in os.environ.get(
    "GEMINI_MODEL", "gemini-3.6-flash,gemini-flash-latest,gemini-2.0-flash"
).split(",") if m.strip()]
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gemini_key.txt")

# Silencia el aviso ruidoso de "automatic function calling".
logging.getLogger("google_genai").setLevel(logging.ERROR)

PROMPT = """\
Sos un extractor de datos. Te paso la foto de un cuadro de salidas de predicacion
(una tabla). Devolveme SOLO texto plano, una salida por linea, con este formato
EXACTO (campos separados por " | "):

fecha hora | salida | territorios | punto de encuentro | conductor

Reglas:
- fecha en formato YYYY-MM-DD. El anio es {anio}. Si el mes/dia hace que la fecha
  quede en otro anio respecto de hoy, usa igual el anio {anio} salvo que el cuadro
  diga otra cosa.
- hora en formato HH:MM de 24 horas (ej: 09:30, 17:00).
- Cada fila de la tabla es una salida. Ojo con las celdas combinadas: la fecha y la
  hora pueden estar escritas una sola vez y valer para varias filas de abajo;
  repetilas en cada linea.
- En la tabla el nombre del dia (martes, miercoles...) y el numero de fecha
  (08-sept) a veces estan en filas distintas pero son el MISMO dia: emparejalos.
- "salida" es la columna Salida (ej: "Congregacional", "Grupo 1", "Grupo La Colonia").
- "territorios" es la columna Territorios, tal cual (si hay dos renglones, unilos con " y ").
- "punto de encuentro" es esa columna. Si dice "a confirmar" o similar, escribi
  exactamente: -- A confirmar --
- "conductor" es la ultima columna (nombre y apellido).
- NO agregues encabezados, numeracion, comillas, viñetas, ni bloques de codigo.
- NO expliques nada. Solo las lineas de datos, en orden cronologico.
"""


def _leer_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key.strip()
    env = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env:
        return env.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as fh:
            k = fh.read().strip()
        if k:
            return k
    raise RuntimeError(
        "Falta la API key de Gemini. Consegui una gratis en "
        "https://aistudio.google.com/apikey y guardala en gemini_key.txt "
        "o exportala como GEMINI_API_KEY."
    )


def guardar_api_key(api_key: str) -> None:
    with open(KEY_FILE, "w", encoding="utf-8") as fh:
        fh.write(api_key.strip() + "\n")
    os.chmod(KEY_FILE, 0o600)


def _limpiar(texto: str) -> str:
    lineas = []
    for cruda in texto.splitlines():
        linea = cruda.strip()
        if not linea:
            continue
        if linea.startswith("```"):  # por si el modelo mete un bloque de codigo
            continue
        lineas.append(linea)
    return "\n".join(lineas) + "\n"


def image_to_txt(image_path: str, api_key: str | None = None,
                 anio: int | None = None) -> str:
    """Devuelve el texto en formato sync.py extraido de la imagen."""
    from google import genai
    from google.genai import types

    anio = anio or dt.date.today().year
    key = _leer_api_key(api_key)

    with open(image_path, "rb") as fh:
        data = fh.read()
    mime = mimetypes.guess_type(image_path)[0] or "image/png"

    from google.genai import errors

    client = genai.Client(api_key=key)
    contents = [
        types.Part.from_bytes(data=data, mime_type=mime),
        PROMPT.format(anio=anio),
    ]

    texto = ""
    ultimo_error: Exception | None = None
    for modelo in MODELOS:
        for intento in range(4):
            try:
                resp = client.models.generate_content(model=modelo, contents=contents)
                texto = (resp.text or "").strip()
                if texto:
                    break
                ultimo_error = RuntimeError("Gemini devolvio una respuesta vacia.")
            except errors.ClientError as e:
                if getattr(e, "status_code", None) == 404:  # modelo inexistente: probar el siguiente
                    ultimo_error = e
                    break
                if getattr(e, "status_code", None) == 429:  # rate limit: esperar y reintentar
                    ultimo_error = e
                    time.sleep(2 * (intento + 1))
                    continue
                raise
            except errors.ServerError as e:  # 503 alta demanda, 500: reintentar
                ultimo_error = e
                time.sleep(2 * (intento + 1))
                continue
        else:
            continue  # se agotaron los reintentos de este modelo
        if texto:
            break
    else:
        raise RuntimeError(
            f"No se pudo transcribir la imagen (ultimo error: {ultimo_error}). "
            "Suele ser demanda alta y temporal: reintenta en un rato."
        )

    encabezado = (
        f"# Generado por Gemini desde {os.path.basename(image_path)} "
        f"el {dt.date.today().isoformat()}\n"
        "# Revisa que este todo bien antes de sincronizar.\n\n"
    )
    return encabezado + _limpiar(texto)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: python extract.py <imagen> [anio]")
    anio = int(sys.argv[2]) if len(sys.argv) > 2 else None
    sys.stdout.write(image_to_txt(sys.argv[1], anio=anio))


if __name__ == "__main__":
    main()
