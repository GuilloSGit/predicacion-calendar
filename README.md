# predicacion-calendar

Toma el **cuadro de salidas de predicacion** (una foto, texto pegado o un archivo) y
lo sincroniza con un calendario **"Predicacion"** en tu Google Calendar. Despues podes
preguntarle a Google ("Hey Google, que tengo el martes?") y te lo lee.

Dos formas de usarlo:

- **Interfaz** (`gui.py` / doble clic en `abrir.command`): cargas la foto del cuadro,
  Gemini (la IA de Google) lo transcribe, revisas y sincronizas.
- **Consola** (`sync.py`): le pasas el cuadro ya en texto.

- Crea un calendario aparte (`Predicacion`), no ensucia el principal.
- Cada salida = un evento con lugar (para navegar con Maps) y aviso 30 min antes.
- Es **idempotente**: si volves a correrlo con el cuadro corregido, borra los eventos
  viejos de esa misma semana y los vuelve a crear. No duplica.

---

## 1. Instalar

```bash
cd ~/Projects/predicacion-calendar
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 2. Credenciales de Google (una sola vez)

El script entra a tu cuenta con OAuth. Necesitas un "client secret":

1. Entra a <https://console.cloud.google.com/> con tu cuenta de Google.
2. Crea un proyecto (arriba, selector de proyecto -> "Proyecto nuevo"). Nombre: `predicacion-calendar`.
3. **APIs y servicios -> Biblioteca** -> busca **Google Calendar API** -> **Habilitar**.
4. **APIs y servicios -> Pantalla de consentimiento de OAuth**:
   - Tipo de usuario: **Externo** -> Crear.
   - Completa nombre de la app y tu email. Guarda y continua hasta el final.
   - En **Usuarios de prueba** agrega tu propio correo (`guillermoandrada@gmail.com`).
     (Con la app en modo "Prueba" alcanza; no hace falta publicarla.)
5. **APIs y servicios -> Credenciales -> Crear credenciales -> ID de cliente de OAuth**:
   - Tipo de aplicacion: **Aplicacion de escritorio**.
   - Crear -> **Descargar JSON**.
6. Guarda ese archivo en esta carpeta como **`credentials.json`**.

`credentials.json` y `token.json` estan en `.gitignore`: no se suben nunca.

La primera corrida abre el navegador para autorizar y deja guardado `token.json`
(despues ya no vuelve a pedir login).

Si la app esta en modo *Testing* en la pantalla de consentimiento, el token vence a
los 7 dias: `sync.py` lo detecta (`invalid_grant`) y vuelve a abrir el navegador solo.
Para evitarlo, pasa la app a **In production** (uso personal, no requiere verificacion).

## 3. API key de Gemini (solo para la interfaz)

La interfaz usa Gemini para leer la foto del cuadro. Necesitas una API key gratis:

1. Entra a <https://aistudio.google.com/apikey> con tu cuenta de Google.
2. **Crear clave de API** (podes usar el mismo proyecto `sync-salidas`).
3. Copiala. La primera vez que toques "Generar texto con Gemini" la app te la pide
   y la guarda en `gemini_key.txt` (esta en `.gitignore`, no se sube).

## 4. Interfaz

```bash
./venv/bin/python gui.py
```

o doble clic en **`abrir.command`**.

Pasos en la ventana:

1. **Cargar imagen…** o **Pegar del portapapeles** (sacas un screenshot del cuadro y lo pegas).
2. Revisa el **Año** y toca **⚡ Generar texto con Gemini**.
3. El cuadro aparece como texto abajo. **Revisalo y corregi** lo que haga falta
   (nombres, territorios, un punto de encuentro mal leido…). Podes tocar
   **Previsualizar** para ver como quedan las salidas.
4. **✅ Sincronizar con Google Calendar**. La primera vez abre el navegador para autorizar.

## 5. Consola

Crea `mi-semana.txt` (ignorado por git) con una salida por linea:

```
fecha+hora | salida | territorios | punto de encuentro | conductor | [duracion_min]
```

Ejemplo:

```
2026-09-08 09:30 | Congregacional | Comenzar T-24 | Uruguay entrada Barrio Santa Teresita | Juan Pérez
```

- Lineas vacias y las que empiezan con `#` se ignoran.
- La fecha acepta `2026-09-08` o `08-sept` (sin anio: toma el mas cercano).
- El ultimo campo (duracion en minutos) es opcional; por defecto **120**.
- Tambien acepta campos separados por TAB, por si copias desde una planilla.

Probar sin tocar nada:

```bash
./venv/bin/python sync.py mi-semana.txt --dry-run
```

Sincronizar de verdad:

```bash
./venv/bin/python sync.py mi-semana.txt
```

Pegar desde el portapapeles (macOS):

```bash
pbpaste | ./venv/bin/python sync.py
```

Opciones utiles: `--calendar-name`, `--tz` (por defecto `America/Argentina/San_Juan`),
`--duration`, `--reminder`, `--dry-run`.

## 6. Que Google lo lea ("Hey Google")

1. En el celular, abri **Google Calendar** -> Ajustes -> calendario **Predicacion**
   -> activa **Sincronizacion / Mostrar**.
2. El Asistente de Google usa tu Google Calendar, asi que ya con eso responde a
   "Hey Google, que tengo manana?" / "...el martes?" / "cual es mi proximo evento?".
3. Si usas varias cuentas en el telefono, asegurate de que el Asistente este en la
   misma cuenta donde se creo el calendario.

## 7. Correr los tests

```bash
./venv/bin/python test_parse.py
```

## Archivos

| archivo | que es |
|---|---|
| `gui.py` | interfaz de escritorio (tkinter) |
| `abrir.command` | doble clic para abrir la interfaz |
| `extract.py` | imagen del cuadro -> texto, via Gemini |
| `sync.py` | parseo del texto + Google Calendar (tambien CLI) |
| `test_parse.py` | tests del parser |
| `requirements.txt` | dependencias |
| `credentials.json` | (lo pones vos) client secret de OAuth — no se sube |
| `token.json` | (se crea solo) sesion de Google Calendar — no se sube |
| `gemini_key.txt` | (se crea solo) API key de Gemini — no se sube |
