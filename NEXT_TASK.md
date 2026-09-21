# NEXT_TASK — Prompt para la próxima sesión

Última actualización: 2026-09-21

```
Proyecto: ~/Projects/predicacion-calendar (Python, sin remoto; cierre = commit local).
Sincroniza el cuadro de salidas de predicación (foto -> Gemini -> texto -> Google Calendar "Predicacion").

ESTADO: funciona end-to-end. Correr: ./venv/bin/python gui.py (o abrir.command); consola: sync.py <archivo.txt>.
Tests: ./venv/bin/python -m py_compile *.py && ./venv/bin/python test_parse.py (7 ok).

COMPLETADO (2026-09-21): la sync falló con RefreshError invalid_grant (token vencido, consent screen en
Testing = 7 días). Fix en sync.py get_service: ante RefreshError descarta creds y relanza el flujo del
navegador. No probado en vivo (requiere login del usuario).

PRÓXIMO:
1. Confirmar que el usuario pudo sincronizar las 10 salidas del 22-27 sept 2026 tras reautorizar.
3. Si vuelve a fallar, revisar que token.json se reescriba y que gui.py muestre el error legible.

CONTEXTO: modelos Gemini en cascada en extract.py (MODELOS); key en gemini_key.txt; credentials.json,
token.json y gemini_key.txt están gitignored. Nunca agregar Co-Authored-By/atribución a Claude en commits.
```
