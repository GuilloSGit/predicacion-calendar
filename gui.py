#!/usr/bin/env python3
"""Interfaz de escritorio (tkinter) para predicacion-calendar.

Flujo:
    1. Cargas la imagen del cuadro de salidas (archivo o portapapeles).
    2. "Generar texto con Gemini" -> la IA de Google transcribe el cuadro.
    3. Revisas / corriges el texto.
    4. "Sincronizar con Google Calendar" -> crea/actualiza los eventos.

Correr:  ./venv/bin/python gui.py
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import os
import queue
import tempfile
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import extract
import sync as sync_mod

BASE = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS = os.path.join(BASE, "credentials.json")
TOKEN = os.path.join(BASE, "token.json")
CAL_NAME = sync_mod.DEFAULT_CALENDAR_NAME
TZ = sync_mod.DEFAULT_TZ
REMINDER_MIN = sync_mod.DEFAULT_REMINDER_MIN

PLACEHOLDER = (
    "# 1) Carga la imagen del cuadro arriba.\n"
    "# 2) Toca \"Generar texto con Gemini\".\n"
    "# 3) Revisa que este todo bien aca.\n"
    "# 4) Toca \"Sincronizar con Google Calendar\".\n"
    "#\n"
    "# Tambien podes escribir a mano, una salida por linea:\n"
    "# 2026-09-08 09:30 | Congregacional | Comenzar T-24 | Uruguay y Santa Teresita | Juan Pérez\n"
)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.busy = False
        self.image_path: str | None = None
        self._thumb = None

        root.title("Predicacion → Google Calendar")
        root.geometry("860x780")
        root.minsize(720, 620)

        pad = {"padx": 10, "pady": 6}

        # --- Fila 1: imagen -------------------------------------------------
        top = ttk.LabelFrame(root, text="1. Imagen del cuadro")
        top.pack(fill="x", **pad)

        btns = ttk.Frame(top)
        btns.pack(side="left", padx=8, pady=8)
        ttk.Button(btns, text="Cargar imagen…", command=self.cargar_imagen).pack(fill="x", pady=2)
        ttk.Button(btns, text="Pegar del portapapeles", command=self.pegar_imagen).pack(fill="x", pady=2)

        self.thumb_lbl = ttk.Label(top, text="(sin imagen)", anchor="center", width=28)
        self.thumb_lbl.pack(side="left", padx=8, pady=8)

        self.img_info = ttk.Label(top, text="", foreground="#666")
        self.img_info.pack(side="left", padx=8)

        # --- Fila 2: generar ---------------------------------------------------
        gen = ttk.LabelFrame(root, text="2. Transcribir con Gemini")
        gen.pack(fill="x", **pad)
        ttk.Label(gen, text="Año:").pack(side="left", padx=(10, 4), pady=8)
        self.anio_var = tk.StringVar(value=str(dt.date.today().year))
        ttk.Entry(gen, textvariable=self.anio_var, width=6).pack(side="left", pady=8)
        self.btn_gen = ttk.Button(gen, text="⚡ Generar texto con Gemini", command=self.generar)
        self.btn_gen.pack(side="left", padx=12, pady=8)

        # --- Fila 3: texto ---------------------------------------------------
        mid = ttk.LabelFrame(root, text="3. Cuadro en texto (editable)")
        mid.pack(fill="both", expand=True, **pad)
        self.txt = scrolledtext.ScrolledText(mid, font=("Menlo", 12), height=14, wrap="none")
        self.txt.pack(fill="both", expand=True, padx=8, pady=8)
        self.txt.insert("1.0", PLACEHOLDER)

        # --- Fila 4: acciones ----------------------------------------------
        act = ttk.Frame(root)
        act.pack(fill="x", **pad)
        self.btn_prev = ttk.Button(act, text="Previsualizar", command=self.previsualizar)
        self.btn_prev.pack(side="left")
        self.btn_save = ttk.Button(act, text="Guardar .txt…", command=self.guardar_txt)
        self.btn_save.pack(side="left", padx=6)
        self.btn_sync = ttk.Button(act, text="✅ Sincronizar con Google Calendar", command=self.sincronizar)
        self.btn_sync.pack(side="right")

        # --- Fila 5: log ---------------------------------------------------
        logf = ttk.LabelFrame(root, text="Registro")
        logf.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(logf, font=("Menlo", 11), height=9,
                                             state="disabled", background="#111", foreground="#ddd")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

        self._action_buttons = [self.btn_gen, self.btn_prev, self.btn_save, self.btn_sync]
        self.root.after(100, self._drain)
        self._log(f"Proyecto: {BASE}\nCalendario destino: '{CAL_NAME}'  |  zona: {TZ}\n")

    # ------------------------------------------------------------------ utils
    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text if text.endswith("\n") else text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for b in self._action_buttons:
            b.configure(state=state)
        self.root.configure(cursor="watch" if busy else "")

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", payload)
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "done":
                    cb, arg = payload
                    self._set_busy(False)
                    cb(arg)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _run_async(self, work, on_done) -> None:
        if self.busy:
            return
        self._set_busy(True)

        class QWriter(io.TextIOBase):
            def write(w, s):  # noqa: N805
                if s:
                    self.q.put(("log", s))
                return len(s)

        def target():
            try:
                with contextlib.redirect_stdout(QWriter()):
                    result = work()
                self.q.put(("done", (on_done, ("ok", result))))
            except Exception as e:  # noqa: BLE001
                self.q.put(("log", "\n" + traceback.format_exc() + "\n"))
                self.q.put(("done", (on_done, ("error", e))))

        threading.Thread(target=target, daemon=True).start()

    def _texto(self) -> str:
        return self.txt.get("1.0", "end").strip()

    def _set_texto(self, s: str) -> None:
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", s)

    def _set_imagen(self, path: str, origen: str) -> None:
        self.image_path = path
        self.img_info.configure(text=f"{origen}\n{os.path.basename(path)}")
        try:
            from PIL import Image, ImageTk

            im = Image.open(path)
            im.thumbnail((220, 130))
            self._thumb = ImageTk.PhotoImage(im)
            self.thumb_lbl.configure(image=self._thumb, text="")
        except Exception:  # noqa: BLE001
            self.thumb_lbl.configure(text="(imagen cargada)", image="")
        self._log(f"Imagen: {path}")

    # ---------------------------------------------------------------- acciones
    def cargar_imagen(self) -> None:
        path = filedialog.askopenfilename(
            title="Elegi la imagen del cuadro",
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("Todos", "*.*")],
        )
        if path:
            self._set_imagen(path, "Archivo")

    def pegar_imagen(self) -> None:
        try:
            from PIL import ImageGrab
        except Exception:  # noqa: BLE001
            messagebox.showerror("Falta Pillow", "Instala las dependencias: pip install -r requirements.txt")
            return
        data = ImageGrab.grabclipboard()
        if isinstance(data, list) and data:
            self._set_imagen(data[0], "Portapapeles (archivo)")
            return
        if data is not None and hasattr(data, "save"):
            tmp = os.path.join(tempfile.gettempdir(),
                               f"cuadro_{dt.datetime.now():%Y%m%d_%H%M%S}.png")
            data.save(tmp)
            self._set_imagen(tmp, "Portapapeles")
            return
        messagebox.showinfo("Sin imagen", "No hay ninguna imagen en el portapapeles.")

    def generar(self) -> None:
        if not self.image_path:
            messagebox.showwarning("Falta la imagen", "Primero carga la imagen del cuadro.")
            return
        try:
            anio = int(self.anio_var.get())
        except ValueError:
            messagebox.showwarning("Año invalido", "El año debe ser un numero, ej: 2026.")
            return
        self._log("\n⚡ Enviando imagen a Gemini…")
        path = self.image_path
        self._run_async(lambda: extract.image_to_txt(path, anio=anio), self._generar_listo)

    def _generar_listo(self, res) -> None:
        status, payload = res
        if status == "ok":
            self._set_texto(payload)
            self._log("✓ Texto generado. Revisalo y luego previsualiza o sincroniza.")
            self.previsualizar(silencioso=True)
            return
        if isinstance(payload, RuntimeError) and "API key" in str(payload):
            key = simpledialog.askstring(
                "API key de Gemini",
                "Pega tu API key de Gemini\n(https://aistudio.google.com/apikey):",
                show="*", parent=self.root,
            )
            if key:
                extract.guardar_api_key(key)
                self._log("API key guardada. Toca \"Generar texto con Gemini\" de nuevo.")
            return
        messagebox.showerror("Error al generar", str(payload))

    def previsualizar(self, silencioso: bool = False) -> None:
        texto = self._texto()
        if not texto:
            if not silencioso:
                messagebox.showinfo("Vacio", "No hay texto para previsualizar.")
            return
        try:
            salidas = sync_mod.parse_schedule(texto)
        except ValueError as e:
            self._log(f"✗ {e}")
            if not silencioso:
                messagebox.showerror("Formato invalido", str(e))
            return
        self._log(f"\n✓ {len(salidas)} salida(s) reconocida(s):")
        for s in salidas:
            self._log(f"   {s.fecha} {s.hora.strftime('%H:%M')}  {s.salida} / "
                      f"{s.territorios} / {s.punto or '(sin lugar)'} / {s.conductor}")

    def guardar_txt(self) -> None:
        texto = self._texto()
        if not texto:
            return
        nombre = "semana.txt"
        try:
            salidas = sync_mod.parse_schedule(texto)
            if salidas:
                nombre = f"semana-{min(s.fecha for s in salidas)}.txt"
        except ValueError:
            pass
        path = filedialog.asksaveasfilename(
            title="Guardar cuadro", defaultextension=".txt",
            initialdir=BASE, initialfile=nombre,
            filetypes=[("Texto", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(texto + "\n")
            self._log(f"Guardado en {path}")

    def sincronizar(self) -> None:
        texto = self._texto()
        try:
            salidas = sync_mod.parse_schedule(texto)
        except ValueError as e:
            messagebox.showerror("Formato invalido", str(e))
            return
        if not salidas:
            messagebox.showinfo("Vacio", "No hay salidas para sincronizar.")
            return
        if not os.path.exists(CREDENTIALS) and not os.path.exists(TOKEN):
            messagebox.showerror(
                "Faltan credenciales",
                f"No encuentro credentials.json en:\n{BASE}\n\nVer README.md, seccion 2.",
            )
            return
        dmin, dmax = min(s.fecha for s in salidas), max(s.fecha for s in salidas)
        if not messagebox.askyesno(
            "Confirmar",
            f"Se van a sincronizar {len(salidas)} salida(s) entre {dmin} y {dmax} "
            f"en el calendario '{CAL_NAME}'.\n\n"
            "Los eventos previos de ese rango (creados por esta app) se reemplazan.\n\nContinuar?",
        ):
            return

        self._log("\n✅ Sincronizando… (puede abrirse el navegador para autorizar)")

        def work():
            service = sync_mod.get_service(CREDENTIALS, TOKEN)
            cid = sync_mod.ensure_calendar(service, CAL_NAME, TZ)
            sync_mod.sync(service, cid, salidas, TZ, REMINDER_MIN, dry_run=False)
            return len(salidas)

        self._run_async(work, self._sync_listo)

    def _sync_listo(self, res) -> None:
        status, payload = res
        if status == "ok":
            self._log(f"\n✓ Listo: {payload} evento(s) sincronizado(s).")
            messagebox.showinfo("Listo", f"{payload} evento(s) sincronizado(s) en '{CAL_NAME}'.")
        else:
            messagebox.showerror("Error al sincronizar", str(payload))


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("aqua")  # nativo en macOS
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
