# /cierre — predicacion-calendar

Cierre de sesion para **predicacion-calendar** (`~/Projects/predicacion-calendar/`).

Proyecto de un solo repo, **sin remoto** configurado: el cierre termina en un commit
local prolijo. No hay paso de push (si algun dia se agrega un remoto, sumar el push
al final, preguntando antes).

Ejecutar los pasos en orden. Si la verificacion (paso 4) falla, no se commitea.

---

## 1. Estado git

```bash
cd ~/Projects/predicacion-calendar
git status
git diff --stat
git log --oneline -5
```

## 2. Actualizar memoria del proyecto

Archivo: `~/.claude/projects/-Users-guillermoandrada/memory/project_predicacion_calendar.md`
(indice en `MEMORY.md` de esa carpeta).

Revisar y dejar al dia:
- Que se hizo esta sesion y que se decidio.
- Estado real (que funciona end-to-end, que quedo pendiente).
- Cambios de plan o de herramientas (modelo de Gemini, scopes, etc.).
- Credenciales / setup de Google Cloud si cambio algo.

## 3. Actualizar documentacion del repo

Solo `README.md`, y solo las secciones donde algo cambio. No reescribir lo que ya
esta bien. Cosas a chequear que sigan ciertas:
- Pasos de setup (venv, Google Cloud, API key de Gemini).
- Modelo/SDK de Gemini en uso (`extract.py` -> `MODELOS`).
- Tabla de archivos al final.

## 4. Verificacion obligatoria

```bash
cd ~/Projects/predicacion-calendar
./venv/bin/python -m py_compile *.py          # compila todo
./venv/bin/python test_parse.py               # 7 tests del parser, sin red
```

Ambos tienen que pasar. El camino Gemini/Calendar necesita red + credenciales y no
se testea en el cierre; si se toco `extract.py` o `sync.py` en la logica de red,
probar a mano al menos una vez:

```bash
./venv/bin/python extract.py <alguna-imagen> 2026 | ./venv/bin/python sync.py --dry-run
```

## 5. Commit (sin push)

Conventional Commits, en español o inglés segun venga el historial. Ejemplo:

```bash
git add -A
git commit -m "feat: interfaz tkinter con transcripcion por Gemini"
```

No hay remoto: el cierre termina aca. No pushear.

## 6. Prompt para la proxima sesion

Dejar en el resumen final un prompt autonomo y completo: que esta hecho, que sigue,
como correr las cosas (`./venv/bin/python gui.py`, `sync.py`, tests), y cualquier
pendiente conocido (ej. quirks de OCR, modelos de Gemini que se cayeron, etc.).
