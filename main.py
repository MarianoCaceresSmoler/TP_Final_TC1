"""
GUI para graficar CSV de osciloscopio - TC1

Requisitos:
    pip install pandas numpy matplotlib
Opcional para arrastrar y soltar archivos:
    pip install tkinterdnd2

Ejecucion:
    python gui_osciloscopio_tc1.py

Formato esperado del CSV del osciloscopio:
    x-axis,1,2,3,4
    second,Volt,Volt,Volt,Volt
    -84.48E-06,0.0E+00,4.70E+00,4.99E+00,5.01E+00

Tambien intenta leer CSV comunes con o sin encabezado.
"""

from __future__ import annotations

import csv
import os
import re
import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Optional

import matplotlib
matplotlib.use("TkAgg")

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    TkinterDnD = None
    DND_FILES = None


X_UNITS = {
    "s": 1.0,
    "ms": 1e3,
    "us": 1e6,
    "µs": 1e6,
    "ns": 1e9,
}

Y_UNITS = {
    "V": 1.0,
    "mV": 1e3,
}

DEFAULT_COLORS = [
    "tab:blue", "tab:orange", "tab:green", "tab:red",
    "tab:purple", "tab:brown", "tab:pink", "tab:gray",
]


@dataclass
class ChannelControls:
    name: str
    enabled: tk.BooleanVar
    scale: tk.StringVar
    offset: tk.StringVar
    color: tk.StringVar


@dataclass
class CursorItem:
    cursor_id: int
    channel: str
    x: float
    y: float
    color: str


class OscilloscopeCSVGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Graficador de CSV de Osciloscopio - TC1")
        self.root.geometry("1320x820")
        self.root.minsize(1100, 700)

        self.file_path: Optional[str] = None
        self.raw_df: Optional[pd.DataFrame] = None
        self.units_row: list[str] = []
        self.time: Optional[np.ndarray] = None
        self.channels: dict[str, np.ndarray] = {}
        self.controls: dict[str, ChannelControls] = {}

        self.cursor_mode = tk.BooleanVar(value=False)
        self.move_cursor_mode = tk.BooleanVar(value=False)
        self.dragging_cursor = False
        self.cursors: list[CursorItem] = []
        self.cursor_artists = []
        self.next_cursor_id = 1
        self.selected_cursor_id: Optional[int] = None
        self.pick_cid = None

        self._build_variables()
        self._build_layout()
        self._connect_events()
        self._plot_empty()

    def _build_variables(self) -> None:
        self.title_var = tk.StringVar(value="Datos del osciloscopio")
        self.xlabel_var = tk.StringVar(value="Tiempo")
        self.ylabel_var = tk.StringVar(value="Tensión")
        self.x_unit_var = tk.StringVar(value="µs")
        self.y_unit_var = tk.StringVar(value="V")
        self.grid_var = tk.BooleanVar(value=True)
        self.grid_x_step_var = tk.StringVar(value="")
        self.grid_y_step_var = tk.StringVar(value="")
        self.log_x_var = tk.BooleanVar(value=False)
        self.log_y_var = tk.BooleanVar(value=False)
        self.mark_max_var = tk.BooleanVar(value=False)
        self.mark_min_var = tk.BooleanVar(value=False)
        self.xy_mode_var = tk.BooleanVar(value=False)
        self.xy_x_var = tk.StringVar(value="")
        self.xy_y_var = tk.StringVar(value="")
        self.cursor_channel_var = tk.StringVar(value="")
        self.cursor_x_var = tk.StringVar(value="")
        self.cursor_y_var = tk.StringVar(value="")
        self.cursor_ref_var = tk.StringVar(value="Ninguno")
        self.status_var = tk.StringVar(value="Cargá un archivo .csv")

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        file_box = ttk.LabelFrame(left, text="Archivo")
        file_box.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(file_box, text="Abrir CSV", command=self.open_file).pack(fill=tk.X, padx=8, pady=6)
        self.file_label = ttk.Label(file_box, text="Ningún archivo cargado", wraplength=260)
        self.file_label.pack(fill=tk.X, padx=8, pady=(0, 6))

        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        else:
            ttk.Label(
                file_box,
                text="Drag & drop desactivado: instalá tkinterdnd2 si lo querés usar.",
                wraplength=260,
            ).pack(fill=tk.X, padx=8, pady=(0, 8))

        labels_box = ttk.LabelFrame(left, text="Título y ejes")
        labels_box.pack(fill=tk.X, pady=(0, 8))
        self._entry(labels_box, "Título", self.title_var)
        self._entry(labels_box, "Eje X", self.xlabel_var)
        self._entry(labels_box, "Eje Y", self.ylabel_var)

        units_frame = ttk.Frame(labels_box)
        units_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(units_frame, text="Unidad X").grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(units_frame, self.x_unit_var, self.x_unit_var.get(), *X_UNITS.keys(), command=lambda _: self.update_plot()).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(units_frame, text="Unidad Y").grid(row=1, column=0, sticky="w")
        ttk.OptionMenu(units_frame, self.y_unit_var, self.y_unit_var.get(), *Y_UNITS.keys(), command=lambda _: self.update_plot()).grid(row=1, column=1, sticky="ew", padx=4)
        units_frame.columnconfigure(1, weight=1)

        grid_box = ttk.LabelFrame(left, text="Grilla y escalas")
        grid_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(grid_box, text="Mostrar grilla", variable=self.grid_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        self._entry(grid_box, "Paso grilla X", self.grid_x_step_var)
        self._entry(grid_box, "Paso grilla Y", self.grid_y_step_var)
        ttk.Checkbutton(grid_box, text="Escala logarítmica X", variable=self.log_x_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(grid_box, text="Escala logarítmica Y", variable=self.log_y_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)

        markers_box = ttk.LabelFrame(left, text="Puntos importantes")
        markers_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(markers_box, text="Marcar máximos", variable=self.mark_max_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(markers_box, text="Marcar mínimos", variable=self.mark_min_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)

        cursor_box = ttk.LabelFrame(left, text="Cursores")
        cursor_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(cursor_box, text="Agregar cursor con clic", variable=self.cursor_mode, command=self._toggle_cursor_mode).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(cursor_box, text="Mover cursor seleccionado", variable=self.move_cursor_mode, command=self._toggle_move_cursor_mode).pack(anchor="w", padx=8, pady=2)

        cursor_channel_row = ttk.Frame(cursor_box)
        cursor_channel_row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(cursor_channel_row, text="Canal:").pack(side=tk.LEFT)
        self.cursor_channel_menu = ttk.OptionMenu(cursor_channel_row, self.cursor_channel_var, "")
        self.cursor_channel_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        coords = ttk.Frame(cursor_box)
        coords.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(coords, text="X").grid(row=0, column=0, sticky="w")
        ttk.Entry(coords, textvariable=self.cursor_x_var, width=10).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Label(coords, text="Y auto").grid(row=0, column=2, sticky="w")
        y_label = ttk.Label(coords, textvariable=self.cursor_y_var, width=11, relief=tk.SUNKEN, anchor="e")
        y_label.grid(row=0, column=3, sticky="ew", padx=3)
        coords.columnconfigure(1, weight=1)
        coords.columnconfigure(3, weight=1)

        refrow = ttk.Frame(cursor_box)
        refrow.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(refrow, text="Comparar con:").pack(side=tk.LEFT)
        self.cursor_ref_menu = ttk.OptionMenu(refrow, self.cursor_ref_var, "Ninguno")
        self.cursor_ref_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        buttons = ttk.Frame(cursor_box)
        buttons.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(buttons, text="Agregar", command=self._add_cursor_from_entries).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(buttons, text="Actualizar", command=self._update_selected_cursor_from_entries).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(buttons, text="Borrar", command=self._delete_selected_cursor).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        self.cursor_tree = ttk.Treeview(
            cursor_box,
            columns=("canal", "color", "x", "y", "dx", "dy"),
            show="headings",
            height=6,
        )
        for col, title, width in [
            ("canal", "Canal", 58),
            ("color", "Color", 55),
            ("x", "X", 62),
            ("y", "Y", 62),
            ("dx", "ΔX", 62),
            ("dy", "ΔY", 62),
        ]:
            self.cursor_tree.heading(col, text=title)
            self.cursor_tree.column(col, width=width, stretch=False)
        self.cursor_tree.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.cursor_tree.bind("<<TreeviewSelect>>", self._on_cursor_select)

        xy_box = ttk.LabelFrame(left, text="Modo XY / Lissajous")
        xy_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(xy_box, text="Activar modo XY", variable=self.xy_mode_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        row = ttk.Frame(xy_box)
        row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row, text="X:").grid(row=0, column=0, sticky="w")
        self.xy_x_menu = ttk.OptionMenu(row, self.xy_x_var, "")
        self.xy_x_menu.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(row, text="Y:").grid(row=1, column=0, sticky="w")
        self.xy_y_menu = ttk.OptionMenu(row, self.xy_y_var, "")
        self.xy_y_menu.grid(row=1, column=1, sticky="ew", padx=4)
        row.columnconfigure(1, weight=1)

        ttk.Button(left, text="Actualizar gráfico", command=self.update_plot).pack(fill=tk.X, pady=(0, 8))
        ttk.Label(left, textvariable=self.status_var, wraplength=280).pack(fill=tk.X)

        self.channel_box = ttk.LabelFrame(left, text="Canales: activar, escala, offset y color")
        self.channel_box.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.channel_canvas = tk.Canvas(self.channel_box, width=300, highlightthickness=0)
        self.channel_scroll = ttk.Scrollbar(self.channel_box, orient="vertical", command=self.channel_canvas.yview)
        self.channel_inner = ttk.Frame(self.channel_canvas)
        self.channel_inner.bind("<Configure>", lambda e: self.channel_canvas.configure(scrollregion=self.channel_canvas.bbox("all")))
        self.channel_canvas.create_window((0, 0), window=self.channel_inner, anchor="nw")
        self.channel_canvas.configure(yscrollcommand=self.channel_scroll.set)
        self.channel_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.channel_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(right)
        toolbar_frame.pack(fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

    def _entry(self, parent: ttk.Frame, label: str, var: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(frame, text=label, width=13).pack(side=tk.LEFT)
        ent = ttk.Entry(frame, textvariable=var)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ent.bind("<Return>", lambda _e: self.update_plot())

    def _connect_events(self) -> None:
        self.pick_cid = self.fig.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_plot_motion)
        self.fig.canvas.mpl_connect("button_release_event", self._on_plot_release)
        self.root.bind("<Left>", lambda e: self._move_selected_cursor_by_key(-1))
        self.root.bind("<Right>", lambda e: self._move_selected_cursor_by_key(1))

    def _plot_empty(self) -> None:
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Cargá un CSV para comenzar", ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_axis_off()
        self.canvas.draw_idle()

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar CSV",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if path:
            self.load_file(path)

    def _on_drop(self, event) -> None:
        raw = event.data.strip()
        paths = self.root.tk.splitlist(raw)
        if paths:
            self.load_file(paths[0])

    def load_file(self, path: str) -> None:
        path = os.path.abspath(path)
        if not path.lower().endswith(".csv"):
            messagebox.showwarning("Archivo rechazado", "El archivo seleccionado no tiene extensión .csv")
            self.status_var.set("Archivo rechazado: no es .csv")
            return
        if not os.path.exists(path):
            messagebox.showerror("Error", "El archivo no existe.")
            return

        try:
            time, channels, units = self._read_oscilloscope_csv(path)
        except Exception as exc:
            messagebox.showerror("No se pudo leer el CSV", f"Revisá el formato del archivo.\n\nDetalle: {exc}")
            self.status_var.set("Error al leer el CSV")
            return

        if time.size == 0 or len(channels) == 0:
            messagebox.showerror("CSV vacío", "No se encontraron datos numéricos suficientes.")
            return

        self.file_path = path
        self.time = time
        self.channels = channels
        self.units_row = units
        self.file_label.config(text=os.path.basename(path))
        self.status_var.set(f"Cargado: {len(time)} muestras, {len(channels)} canal(es)")
        self._rebuild_channel_controls()
        self._rebuild_xy_menus()
        self._rebuild_cursor_channel_menu()
        self.cursors.clear()
        self._refresh_cursor_tree()
        self.update_plot()

    def _detect_delimiter(self, path: str) -> str:
        with open(path, "r", newline="", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(4096)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            return dialect.delimiter
        except Exception:
            return ","

    def _read_oscilloscope_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        sep = self._detect_delimiter(path)
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            first_lines = [f.readline().strip() for _ in range(3)]

        # Caso típico del enunciado: primera fila nombres, segunda unidades, datos desde la tercera.
        first = re.split(rf"{re.escape(sep)}", first_lines[0]) if first_lines[0] else []
        second = re.split(rf"{re.escape(sep)}", first_lines[1]) if first_lines[1] else []
        looks_like_scope = bool(first) and first[0].strip().lower() in {"x-axis", "time", "tiempo"}

        if looks_like_scope:
            names = [c.strip() for c in first]
            units = [c.strip() for c in second]
            df = pd.read_csv(path, sep=sep, skiprows=2, header=None, engine="python")
            df = df.apply(pd.to_numeric, errors="coerce").dropna(how="all")
            df = df.dropna(axis=1, how="all")
            if df.shape[1] < 2:
                raise ValueError("el CSV tiene menos de dos columnas numéricas")
            time = df.iloc[:, 0].to_numpy(dtype=float)
            channels = {}
            for i in range(1, df.shape[1]):
                label = names[i] if i < len(names) and names[i] else f"Canal {i}"
                if label.isdigit():
                    label = f"Canal {label}"
                channels[label] = df.iloc[:, i].to_numpy(dtype=float)
            return time, channels, units

        # Fallback: intenta CSV común con encabezado y, si falla, sin encabezado.
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
            numeric = df.apply(pd.to_numeric, errors="coerce")
            if numeric.shape[1] < 2 or numeric.dropna(how="all").empty:
                raise ValueError
            labels = list(df.columns)
        except Exception:
            df = pd.read_csv(path, sep=sep, header=None, engine="python")
            numeric = df.apply(pd.to_numeric, errors="coerce")
            labels = [f"Columna {i+1}" for i in range(numeric.shape[1])]

        numeric = numeric.dropna(how="all").dropna(axis=1, how="all")
        if numeric.shape[1] < 2:
            raise ValueError("el CSV tiene menos de dos columnas numéricas")
        time = numeric.iloc[:, 0].to_numpy(dtype=float)
        channels = {str(labels[i]) if i < len(labels) else f"Canal {i}": numeric.iloc[:, i].to_numpy(dtype=float)
                    for i in range(1, numeric.shape[1])}
        return time, channels, []

    def _rebuild_channel_controls(self) -> None:
        for child in self.channel_inner.winfo_children():
            child.destroy()
        self.controls.clear()

        for idx, name in enumerate(self.channels.keys()):
            box = ttk.Frame(self.channel_inner, padding=4)
            box.pack(fill=tk.X, pady=2)

            enabled = tk.BooleanVar(value=True)
            scale = tk.StringVar(value="1")
            offset = tk.StringVar(value="0")
            color = tk.StringVar(value=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
            self.controls[name] = ChannelControls(name, enabled, scale, offset, color)

            ttk.Checkbutton(box, text=name, variable=enabled, command=self.update_plot).grid(row=0, column=0, columnspan=4, sticky="w")
            ttk.Label(box, text="Escala").grid(row=1, column=0, sticky="w")
            ttk.Entry(box, textvariable=scale, width=8).grid(row=1, column=1, sticky="ew")
            ttk.Label(box, text="Offset").grid(row=1, column=2, sticky="w", padx=(6, 0))
            ttk.Entry(box, textvariable=offset, width=8).grid(row=1, column=3, sticky="ew")
            ttk.Button(box, text="Color", command=lambda n=name: self._choose_color(n)).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(3, 0))

            for v in (scale, offset):
                v.trace_add("write", lambda *_: self._safe_update_plot())
            box.columnconfigure(1, weight=1)
            box.columnconfigure(3, weight=1)

    def _rebuild_xy_menus(self) -> None:
        names = list(self.channels.keys())
        if len(names) >= 2:
            self.xy_x_var.set(names[0])
            self.xy_y_var.set(names[1])
        elif len(names) == 1:
            self.xy_x_var.set(names[0])
            self.xy_y_var.set(names[0])
        else:
            self.xy_x_var.set("")
            self.xy_y_var.set("")

        for menu_widget, var in [(self.xy_x_menu, self.xy_x_var), (self.xy_y_menu, self.xy_y_var)]:
            menu = menu_widget["menu"]
            menu.delete(0, "end")
            for name in names:
                menu.add_command(label=name, command=lambda value=name, v=var: (v.set(value), self.update_plot()))

    def _rebuild_cursor_channel_menu(self) -> None:
        names = list(self.channels.keys())
        if names and self.cursor_channel_var.get() not in names:
            self.cursor_channel_var.set(names[0])
        elif not names:
            self.cursor_channel_var.set("")

        menu = self.cursor_channel_menu["menu"]
        menu.delete(0, "end")
        for name in names:
            menu.add_command(label=name, command=lambda value=name: self.cursor_channel_var.set(value))

    def _rebuild_cursor_ref_menu(self) -> None:
        values = ["Ninguno"] + [f"C{c.cursor_id} - {c.channel}" for c in self.cursors]
        if self.cursor_ref_var.get() not in values:
            self.cursor_ref_var.set("Ninguno")
        menu = self.cursor_ref_menu["menu"]
        menu.delete(0, "end")
        for value in values:
            menu.add_command(label=value, command=lambda v=value: (self.cursor_ref_var.set(v), self._refresh_cursor_tree()))

    def _choose_color(self, channel_name: str) -> None:
        initial = self.controls[channel_name].color.get()
        selected = colorchooser.askcolor(color=initial, title=f"Color para {channel_name}")
        if selected and selected[1]:
            self.controls[channel_name].color.set(selected[1])
            self.update_plot()

    def _safe_float(self, text: str, default: float) -> float:
        try:
            text = text.replace(",", ".").strip()
            return float(text) if text else default
        except Exception:
            return default

    def _safe_update_plot(self) -> None:
        # Evita errores mientras el usuario está escribiendo números incompletos.
        self.root.after_idle(self.update_plot)

    def _transformed_channel(self, name: str) -> np.ndarray:
        y = self.channels[name].astype(float)
        ctrl = self.controls[name]
        scale = self._safe_float(ctrl.scale.get(), 1.0)
        offset = self._safe_float(ctrl.offset.get(), 0.0)
        return y * scale + offset

    def update_plot(self) -> None:
        if self.time is None or not self.channels:
            return

        self.ax.clear()
        self.ax.set_axis_on()
        self.cursor_artists.clear()

        x_factor = X_UNITS.get(self.x_unit_var.get(), 1.0)
        y_factor = Y_UNITS.get(self.y_unit_var.get(), 1.0)

        if self.xy_mode_var.get():
            self._plot_xy(y_factor)
        else:
            x = self.time * x_factor
            for name in self.channels.keys():
                ctrl = self.controls[name]
                if not ctrl.enabled.get():
                    continue
                y = self._transformed_channel(name) * y_factor
                self.ax.plot(x, y, label=name, color=ctrl.color.get())
                self._mark_points(x, y, name, ctrl.color.get())
            self.ax.set_xlabel(f"{self.xlabel_var.get()} [{self.x_unit_var.get()}]")
            self.ax.set_ylabel(f"{self.ylabel_var.get()} [{self.y_unit_var.get()}]")

        self.ax.set_title(self.title_var.get())
        self._apply_grid_and_scales()
        self.ax.legend(loc="best")
        self._redraw_cursors()
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _plot_xy(self, y_factor: float) -> None:
        x_name = self.xy_x_var.get()
        y_name = self.xy_y_var.get()
        if x_name not in self.channels or y_name not in self.channels:
            self.ax.text(0.5, 0.5, "Elegí dos canales válidos", ha="center", va="center", transform=self.ax.transAxes)
            return
        x_data = self._transformed_channel(x_name) * y_factor
        y_data = self._transformed_channel(y_name) * y_factor
        color = self.controls.get(y_name, next(iter(self.controls.values()))).color.get()
        self.ax.plot(x_data, y_data, color=color, label=f"{y_name} vs {x_name}")
        self.ax.set_xlabel(f"{x_name} [{self.y_unit_var.get()}]")
        self.ax.set_ylabel(f"{y_name} [{self.y_unit_var.get()}]")
        self._mark_points(x_data, y_data, y_name, color)

    def _mark_points(self, x: np.ndarray, y: np.ndarray, name: str, color: str) -> None:
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            return
        xf = x[finite]
        yf = y[finite]
        if self.mark_max_var.get():
            idx = int(np.argmax(yf))
            self.ax.scatter([xf[idx]], [yf[idx]], marker="o", color=color)
            self.ax.annotate(f"max {name}\n({xf[idx]:.4g}, {yf[idx]:.4g})", (xf[idx], yf[idx]), textcoords="offset points", xytext=(8, 8), fontsize=8)
        if self.mark_min_var.get():
            idx = int(np.argmin(yf))
            self.ax.scatter([xf[idx]], [yf[idx]], marker="v", color=color)
            self.ax.annotate(f"min {name}\n({xf[idx]:.4g}, {yf[idx]:.4g})", (xf[idx], yf[idx]), textcoords="offset points", xytext=(8, -16), fontsize=8)

    def _apply_grid_and_scales(self) -> None:
        if self.log_x_var.get():
            self.ax.set_xscale("log")
        if self.log_y_var.get():
            self.ax.set_yscale("log")

        if self.grid_var.get():
            self.ax.grid(True, which="both", alpha=0.35)
            x_step = self._safe_float(self.grid_x_step_var.get(), 0.0)
            y_step = self._safe_float(self.grid_y_step_var.get(), 0.0)
            if x_step > 0 and not self.log_x_var.get():
                self.ax.xaxis.set_major_locator(MultipleLocator(x_step))
            if y_step > 0 and not self.log_y_var.get():
                self.ax.yaxis.set_major_locator(MultipleLocator(y_step))
        else:
            self.ax.grid(False)

    def _toggle_cursor_mode(self) -> None:
        if self.cursor_mode.get():
            self.move_cursor_mode.set(False)
            self.status_var.set("Cursores: elegí un canal y hacé clic. Cada clic agrega un cursor; Y se calcula automáticamente.")
        else:
            self.status_var.set("Modo agregar cursor desactivado")

    def _toggle_move_cursor_mode(self) -> None:
        if self.move_cursor_mode.get():
            self.cursor_mode.set(False)
            self.status_var.set("Mover cursor: seleccioná uno en la tabla y movelo con clic/arrastre o flechas izquierda/derecha.")
        else:
            self.dragging_cursor = False
            self.status_var.set("Modo mover cursor desactivado")

    def _on_plot_click(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None:
            return
        if self.xy_mode_var.get():
            if self.cursor_mode.get() or self.move_cursor_mode.get():
                messagebox.showinfo("Cursores", "Los cursores por canal están pensados para el modo temporal, no para modo XY.")
            return

        if self.move_cursor_mode.get():
            cursor = self._selected_cursor()
            if cursor is None:
                messagebox.showwarning("Sin selección", "Seleccioná un cursor de la tabla para moverlo.")
                return
            self.dragging_cursor = True
            self._move_cursor_to_x(cursor, float(event.xdata))
            return

        if self.cursor_mode.get():
            channel = self.cursor_channel_var.get()
            if channel not in self.channels:
                messagebox.showwarning("Canal inválido", "Elegí un canal para el cursor.")
                return
            x = float(event.xdata)
            y = self._interp_channel_y(channel, x)
            self._add_cursor(channel, x, y)

    def _on_plot_motion(self, event) -> None:
        if not self.dragging_cursor or not self.move_cursor_mode.get():
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        cursor = self._selected_cursor()
        if cursor is not None:
            self._move_cursor_to_x(cursor, float(event.xdata))

    def _on_plot_release(self, _event) -> None:
        self.dragging_cursor = False

    def _interp_channel_y(self, channel: str, x_display_units: float) -> float:
        """Devuelve Y del canal en las unidades mostradas, interpolando según X mostrada."""
        x_factor = X_UNITS.get(self.x_unit_var.get(), 1.0)
        y_factor = Y_UNITS.get(self.y_unit_var.get(), 1.0)
        xdata = self.time * x_factor
        ydata = self._transformed_channel(channel) * y_factor
        finite = np.isfinite(xdata) & np.isfinite(ydata)
        if not finite.any():
            return 0.0
        xf = xdata[finite]
        yf = ydata[finite]
        order = np.argsort(xf)
        xf = xf[order]
        yf = yf[order]
        return float(np.interp(x_display_units, xf, yf))

    def _parse_cursor_ref_id(self) -> Optional[int]:
        text = self.cursor_ref_var.get().strip()
        m = re.match(r"C(\d+)\b", text)
        return int(m.group(1)) if m else None

    def _cursor_by_id(self, cursor_id: int) -> Optional[CursorItem]:
        for cursor in self.cursors:
            if cursor.cursor_id == cursor_id:
                return cursor
        return None

    def _selected_cursor(self) -> Optional[CursorItem]:
        if self.selected_cursor_id is None:
            return None
        return self._cursor_by_id(self.selected_cursor_id)

    def _add_cursor(self, channel: str, x: float, y: float) -> None:
        color = self.controls[channel].color.get() if channel in self.controls else "black"
        cursor = CursorItem(self.next_cursor_id, channel, x, y, color)
        self.next_cursor_id += 1
        self.cursors.append(cursor)
        self.selected_cursor_id = cursor.cursor_id
        self.cursor_x_var.set(f"{cursor.x:.8g}")
        self.cursor_y_var.set(f"{cursor.y:.8g}")
        self._refresh_cursor_tree()
        self.update_plot()
        self.status_var.set(f"Agregado cursor C{cursor.cursor_id} en {channel}")

    def _add_cursor_from_entries(self) -> None:
        channel = self.cursor_channel_var.get()
        if channel not in self.channels:
            messagebox.showwarning("Canal inválido", "Elegí un canal válido.")
            return
        try:
            x = float(self.cursor_x_var.get().replace(",", "."))
        except Exception:
            messagebox.showwarning("X inválida", "Escribí una coordenada X numérica.")
            return
        y = self._interp_channel_y(channel, x)
        self._add_cursor(channel, x, y)

    def _update_selected_cursor_from_entries(self) -> None:
        cursor = self._selected_cursor()
        if cursor is None:
            messagebox.showwarning("Sin selección", "Seleccioná un cursor de la tabla para modificarlo.")
            return
        channel = self.cursor_channel_var.get()
        if channel not in self.channels:
            messagebox.showwarning("Canal inválido", "Elegí un canal válido.")
            return
        try:
            x = float(self.cursor_x_var.get().replace(",", "."))
        except Exception:
            messagebox.showwarning("X inválida", "Escribí una coordenada X numérica.")
            return
        cursor.channel = channel
        cursor.color = self.controls[channel].color.get() if channel in self.controls else cursor.color
        self._move_cursor_to_x(cursor, x)
        self.status_var.set(f"Actualizado cursor C{cursor.cursor_id}; Y recalculada automáticamente")

    def _move_cursor_to_x(self, cursor: CursorItem, x: float) -> None:
        cursor.x = x
        cursor.y = self._interp_channel_y(cursor.channel, cursor.x)
        cursor.color = self.controls[cursor.channel].color.get() if cursor.channel in self.controls else cursor.color
        self.selected_cursor_id = cursor.cursor_id
        self.cursor_channel_var.set(cursor.channel)
        self.cursor_x_var.set(f"{cursor.x:.8g}")
        self.cursor_y_var.set(f"{cursor.y:.8g}")
        self._refresh_cursor_tree()
        self.update_plot()

    def _move_selected_cursor_by_key(self, direction: int) -> None:
        if not self.move_cursor_mode.get() or self.xy_mode_var.get():
            return
        cursor = self._selected_cursor()
        if cursor is None or self.time is None:
            return
        x_factor = X_UNITS.get(self.x_unit_var.get(), 1.0)
        xdata = np.asarray(self.time, dtype=float) * x_factor
        finite = np.isfinite(xdata)
        if not finite.any():
            return
        xs = np.sort(np.unique(xdata[finite]))
        idx = int(np.searchsorted(xs, cursor.x))
        if direction < 0:
            idx = max(0, idx - 1)
        else:
            idx = min(len(xs) - 1, idx + 1)
        self._move_cursor_to_x(cursor, float(xs[idx]))

    def _delete_selected_cursor(self) -> None:
        cursor = self._selected_cursor()
        if cursor is None:
            messagebox.showwarning("Sin selección", "Seleccioná un cursor de la tabla para borrarlo.")
            return
        self.cursors = [c for c in self.cursors if c.cursor_id != cursor.cursor_id]
        self.selected_cursor_id = None
        self.cursor_x_var.set("")
        self.cursor_y_var.set("")
        self._refresh_cursor_tree()
        self.update_plot()
        self.status_var.set(f"Borrado cursor C{cursor.cursor_id}")

    def _on_cursor_select(self, _event=None) -> None:
        selected = self.cursor_tree.selection()
        if not selected:
            return
        try:
            cursor_id = int(selected[0])
        except Exception:
            return
        cursor = self._cursor_by_id(cursor_id)
        if cursor is None:
            return
        self.selected_cursor_id = cursor.cursor_id
        self.cursor_channel_var.set(cursor.channel)
        self.cursor_x_var.set(f"{cursor.x:.8g}")
        self.cursor_y_var.set(f"{cursor.y:.8g}")

    def _refresh_cursor_tree(self) -> None:
        if not hasattr(self, "cursor_tree"):
            return
        self._rebuild_cursor_ref_menu()
        for item in self.cursor_tree.get_children():
            self.cursor_tree.delete(item)
        ref = self._cursor_by_id(self._parse_cursor_ref_id()) if self._parse_cursor_ref_id() is not None else None
        for cursor in self.cursors:
            if ref is not None and ref.cursor_id != cursor.cursor_id:
                dx = cursor.x - ref.x
                dy = cursor.y - ref.y
                dx_text = f"{dx:.5g}"
                dy_text = f"{dy:.5g}"
            else:
                dx_text = "-"
                dy_text = "-"
            values = (
                cursor.channel,
                cursor.color,
                f"{cursor.x:.5g}",
                f"{cursor.y:.5g}",
                dx_text,
                dy_text,
            )
            self.cursor_tree.insert("", "end", iid=str(cursor.cursor_id), values=values)
        if self.selected_cursor_id is not None and self.cursor_tree.exists(str(self.selected_cursor_id)):
            self.cursor_tree.selection_set(str(self.selected_cursor_id))



    def _redraw_cursors(self) -> None:
        if self.xy_mode_var.get():
            return

        for cursor in self.cursors:
            color = cursor.color

            selected = cursor.cursor_id == self.selected_cursor_id
            lw = 2.0 if selected else 1.2
            marker_size = 60 if selected else 35

            # Línea vertical: marca la X del cursor
            vline = self.ax.axvline(
                cursor.x,
                linestyle="--",
                linewidth=lw,
                color=color,
                alpha=0.85,
            )

            # Línea horizontal: marca la Y del cursor
            hline = self.ax.axhline(
                cursor.y,
                linestyle=":",
                linewidth=lw,
                color=color,
                alpha=0.85,
            )

            # Punto de intersección sobre la curva
            marker = self.ax.scatter(
                [cursor.x],
                [cursor.y],
                color=color,
                s=marker_size,
                zorder=5,
            )

            text = self.ax.annotate(
                f"C{cursor.cursor_id}\n{cursor.channel}",
                (cursor.x, cursor.y),
                textcoords="offset points",
                xytext=(7, 7),
                fontsize=8,
                color=color,
            )

            self.cursor_artists.extend([vline, hline, marker, text])

    def _clear_cursors(self, draw: bool = True) -> None:
        self.cursors.clear()
        self.selected_cursor_id = None
        self.cursor_x_var.set("")
        self.cursor_y_var.set("")
        self._refresh_cursor_tree()
        if draw:
            self.update_plot()


def main() -> None:
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    # Tema nativo más prolijo si está disponible.
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    app = OscilloscopeCSVGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
