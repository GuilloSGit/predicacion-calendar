#!/bin/bash
# Doble clic para abrir la interfaz.
cd "$(dirname "$0")" || exit 1
exec ./venv/bin/python gui.py
