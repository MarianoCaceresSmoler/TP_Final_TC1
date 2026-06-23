"""
GUI TC1 para CSV de osciloscopio, simulaciones y Bode.

Requisitos:
    py -m pip install pandas numpy matplotlib
Opcional para drag & drop:
    py -m pip install tkinterdnd2

Ejecución:
    py gui_tc1_modo_bode_mejorado.py

Características:
- Modo exclusivo: TIEMPO o BODE. No mezcla ambos sin preguntar.
- Modo TIEMPO: superposición de varios CSV, escala Y, offset Y, offset X, alineación a t=0.
- Modo BODE: magnitud [dB] y fase [°] vs frecuencia [Hz] con eje logarítmico.
- Menú izquierdo en pestañas para que no quede todo apretado.
- Cursores en modo TIEMPO y BODE con Y automática, tabla y comparación ΔX/ΔY.
- Cambio de color por canal desde una tabla clara.
- Exportación del gráfico actual a PDF.
"""

from __future__ import annotations

import csv
import os
import re
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Literal, Optional

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


AppMode = Literal["empty", "time", "bode"]
ChannelKind = Literal["time", "bode_mag", "bode_phase"]

X_UNITS = {"s": 1.0, "ms": 1e3, "us": 1e6, "µs": 1e6, "ns": 1e9}
Y_UNITS = {"V": 1.0, "mV": 1e3}
# Colores en formato HEX.
# Tkinter no entiende nombres de Matplotlib como "tab:blue" en el selector de color,
# por eso usamos HEX: sirven tanto para Tkinter como para Matplotlib.
DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]

@dataclass
class ChannelData:
    name: str
    x: np.ndarray
    y: np.ndarray
    kind: ChannelKind
    source_file: str


@dataclass
class ChannelControls:
    enabled: tk.BooleanVar
    scale_y: tk.StringVar
    offset_y: tk.StringVar
    offset_x: tk.StringVar
    color: tk.StringVar


@dataclass
class CursorItem:
    cursor_id: int
    channel: str
    x: float
    y: float
    color: str


class TC1CSVGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TC1 - Graficador CSV")
        self.root.geometry("1500x900")
        self.root.minsize(1220, 760)

        self.mode: AppMode = "empty"
        self.channels: dict[str, ChannelData] = {}
        self.controls: dict[str, ChannelControls] = {}
        self.loaded_files: list[str] = []

        self.cursors: list[CursorItem] = []
        self.next_cursor_id = 1
        self.selected_cursor_id: Optional[int] = None
        self.dragging_cursor = False
        self.dragging_channel_shift = False
        self.last_shift_x: Optional[float] = None

        self.bode_axes: dict[str, object] = {}

        self._build_vars()
        self._build_layout()
        self._connect_events()
        self._plot_empty()

    # ------------------------------------------------------------------
    # Construcción de interfaz
    # ------------------------------------------------------------------
    def _build_vars(self) -> None:
        self.title_var = tk.StringVar(value="Datos del osciloscopio")
        self.xlabel_var = tk.StringVar(value="Tiempo")
        self.ylabel_var = tk.StringVar(value="Tensión")
        self.x_unit_var = tk.StringVar(value="µs")
        self.y_unit_var = tk.StringVar(value="V")

        self.grid_var = tk.BooleanVar(value=True)
        self.align_time_var = tk.BooleanVar(value=True)
        self.log_x_var = tk.BooleanVar(value=False)
        self.log_y_var = tk.BooleanVar(value=False)
        self.grid_x_step_var = tk.StringVar(value="")
        self.grid_y_step_var = tk.StringVar(value="")
        self.mark_max_var = tk.BooleanVar(value=False)
        self.mark_min_var = tk.BooleanVar(value=False)

        self.xy_mode_var = tk.BooleanVar(value=False)
        self.xy_x_var = tk.StringVar(value="")
        self.xy_y_var = tk.StringVar(value="")

        self.shift_mode_var = tk.BooleanVar(value=False)
        self.shift_channel_var = tk.StringVar(value="")
        self.shift_x_var = tk.StringVar(value="0")

        self.cursor_add_mode = tk.BooleanVar(value=False)
        self.cursor_move_mode = tk.BooleanVar(value=False)
        self.cursor_channel_var = tk.StringVar(value="")
        self.cursor_x_var = tk.StringVar(value="")
        self.cursor_y_var = tk.StringVar(value="")
        self.cursor_ref_var = tk.StringVar(value="Ninguno")

        self.channel_enabled_var = tk.BooleanVar(value=True)
        self.channel_scale_var = tk.StringVar(value="1")
        self.channel_oy_var = tk.StringVar(value="0")
        self.channel_ox_var = tk.StringVar(value="0")

        self.status_var = tk.StringVar(value="Cargá o arrastrá uno o más CSV")
        self.mode_var = tk.StringVar(value="Modo: vacío")

    def _build_layout(self) -> None:
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.Frame(main, width=500)
        right = ttk.Frame(main)
        main.add(left, weight=0)
        main.add(right, weight=1)

        # Notebook lateral: evita una columna interminable.
        self.tabs = ttk.Notebook(left)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        self.tab_files = ttk.Frame(self.tabs, padding=8)
        self.tab_plot = ttk.Frame(self.tabs, padding=8)
        self.tab_channels = ttk.Frame(self.tabs, padding=8)
        self.tab_cursors = ttk.Frame(self.tabs, padding=8)

        self.tabs.add(self.tab_files, text="Archivos")
        self.tabs.add(self.tab_plot, text="Gráfico")
        self.tabs.add(self.tab_channels, text="Canales")
        self.tabs.add(self.tab_cursors, text="Cursores")

        self._build_files_tab()
        self._build_plot_tab()
        self._build_channels_tab()
        self._build_cursors_tab()

        # Área de gráfico.
        self.fig = Figure(figsize=(9.2, 6.2), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(right)
        toolbar_frame.pack(fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        self._set_mode_widgets()

    def _build_files_tab(self) -> None:
        ttk.Button(self.tab_files, text="Agregar CSV", command=self.open_files).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(self.tab_files, text="Limpiar todo", command=self.clear_all).pack(fill=tk.X, pady=6)
        ttk.Button(self.tab_files, text="Guardar gráfico como PDF", command=self.export_pdf).pack(fill=tk.X, pady=6)

        ttk.Separator(self.tab_files).pack(fill=tk.X, pady=10)
        ttk.Label(self.tab_files, textvariable=self.mode_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.file_label = ttk.Label(self.tab_files, text="Sin archivos cargados", wraplength=450)
        self.file_label.pack(fill=tk.X, pady=(4, 10))

        msg = "También podés arrastrar CSV a cualquier parte de la ventana."
        if not DND_AVAILABLE:
            msg = "Drag & drop desactivado. Instalá: py -m pip install tkinterdnd2"
        ttk.Label(self.tab_files, text=msg, wraplength=450).pack(fill=tk.X)

        ttk.Separator(self.tab_files).pack(fill=tk.X, pady=10)
        ttk.Label(
            self.tab_files,
            text=(
                "La aplicación trabaja en modo exclusivo: si cargás un Bode, solo se superponen Bodes; "
                "si cargás señales temporales, solo se superponen señales temporales."
            ),
            wraplength=450,
        ).pack(fill=tk.X)
        ttk.Label(self.tab_files, textvariable=self.status_var, wraplength=450, foreground="#333").pack(fill=tk.X, pady=(12, 0))

        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _build_plot_tab(self) -> None:
        # Título común.
        common = ttk.LabelFrame(self.tab_plot, text="Título")
        common.pack(fill=tk.X, pady=(0, 8))
        self._entry(common, "Título", self.title_var)

        # Opciones específicas para señales temporales.
        self.time_options = ttk.LabelFrame(self.tab_plot, text="Modo tiempo")
        self.time_options.pack(fill=tk.X, pady=(0, 8))
        self._entry(self.time_options, "Eje X", self.xlabel_var)
        self._entry(self.time_options, "Eje Y", self.ylabel_var)
        units = ttk.Frame(self.time_options)
        units.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(units, text="Unidad X", width=12).grid(row=0, column=0, sticky="w")
        ttk.OptionMenu(units, self.x_unit_var, self.x_unit_var.get(), *X_UNITS.keys(), command=lambda _=None: self._unit_changed()).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(units, text="Unidad Y", width=12).grid(row=1, column=0, sticky="w")
        ttk.OptionMenu(units, self.y_unit_var, self.y_unit_var.get(), *Y_UNITS.keys(), command=lambda _=None: self.update_plot()).grid(row=1, column=1, sticky="ew", padx=4)
        units.columnconfigure(1, weight=1)
        ttk.Checkbutton(self.time_options, text="Alinear cada CSV temporal a t = 0", variable=self.align_time_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(self.time_options, text="Marcar máximos", variable=self.mark_max_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(self.time_options, text="Marcar mínimos", variable=self.mark_min_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)

        xy_box = ttk.LabelFrame(self.time_options, text="Modo XY / Lissajous")
        xy_box.pack(fill=tk.X, padx=8, pady=(8, 8))
        ttk.Checkbutton(xy_box, text="Activar modo XY", variable=self.xy_mode_var, command=self._toggle_xy).pack(anchor="w", padx=8, pady=2)
        row = ttk.Frame(xy_box)
        row.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(row, text="X").grid(row=0, column=0, sticky="w")
        self.xy_x_menu = ttk.OptionMenu(row, self.xy_x_var, "")
        self.xy_x_menu.grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(row, text="Y").grid(row=1, column=0, sticky="w")
        self.xy_y_menu = ttk.OptionMenu(row, self.xy_y_var, "")
        self.xy_y_menu.grid(row=1, column=1, sticky="ew", padx=4)
        row.columnconfigure(1, weight=1)

        # Ajuste temporal, solo para modo tiempo.
        self.shift_box = ttk.LabelFrame(self.tab_plot, text="Ajuste temporal / fase")
        self.shift_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(self.shift_box, text="Mover canal seleccionado", variable=self.shift_mode_var, command=self._toggle_shift_mode).pack(anchor="w", padx=8, pady=(6, 2))
        row = ttk.Frame(self.shift_box)
        row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(row, text="Canal", width=12).grid(row=0, column=0, sticky="w")
        self.shift_channel_menu = ttk.OptionMenu(row, self.shift_channel_var, "")
        self.shift_channel_menu.grid(row=0, column=1, sticky="ew", padx=4)
        row.columnconfigure(1, weight=1)
        row2 = ttk.Frame(self.shift_box)
        row2.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(row2, text="Offset X", width=12).grid(row=0, column=0, sticky="w")
        ttk.Entry(row2, textvariable=self.shift_x_var, width=12).grid(row=0, column=1, sticky="ew", padx=4)
        self.shift_x_unit_label = ttk.Label(row2, text="µs")
        self.shift_x_unit_label.grid(row=0, column=2, sticky="w")
        ttk.Button(row2, text="Aplicar", command=self._apply_shift_entry).grid(row=0, column=3, padx=(6, 0))
        row2.columnconfigure(1, weight=1)
        ttk.Label(self.shift_box, text="Mouse: arrastrar horizontalmente. Flechas: una muestra. Shift+flecha: 10 muestras. Ctrl+flecha: 0,1 muestra.", wraplength=450).pack(fill=tk.X, padx=8, pady=(2, 8))

        # Opciones específicas de Bode.
        self.bode_options = ttk.LabelFrame(self.tab_plot, text="Modo Bode")
        self.bode_options.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            self.bode_options,
            text="En Bode se grafica automáticamente magnitud [dB] y fase [°] contra frecuencia [Hz] con eje X logarítmico.",
            wraplength=450,
        ).pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Checkbutton(self.bode_options, text="Mostrar grilla", variable=self.grid_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Label(self.bode_options, text="Los cursores de Bode están en la pestaña Cursores.", wraplength=450).pack(fill=tk.X, padx=8, pady=(4, 8))

        # Opciones comunes de visualización.
        visual = ttk.LabelFrame(self.tab_plot, text="Visualización común")
        visual.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(visual, text="Mostrar grilla", variable=self.grid_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        self._entry(visual, "Paso grilla X", self.grid_x_step_var)
        self._entry(visual, "Paso grilla Y", self.grid_y_step_var)
        self.time_logx_check = ttk.Checkbutton(visual, text="Escala logarítmica X", variable=self.log_x_var, command=self.update_plot)
        self.time_logx_check.pack(anchor="w", padx=8, pady=2)
        self.time_logy_check = ttk.Checkbutton(visual, text="Escala logarítmica Y", variable=self.log_y_var, command=self.update_plot)
        self.time_logy_check.pack(anchor="w", padx=8, pady=2)

    def _build_channels_tab(self) -> None:
        ttk.Label(self.tab_channels, text="Doble clic en un canal para activar/desactivar.").pack(anchor="w", pady=(0, 4))
        self.channel_tree = ttk.Treeview(self.tab_channels, columns=("on", "tipo", "scale", "oy", "ox"), show="tree headings", height=13)
        self.channel_tree.heading("#0", text="Canal")
        self.channel_tree.heading("on", text="On")
        self.channel_tree.heading("tipo", text="Tipo")
        self.channel_tree.heading("scale", text="Esc Y")
        self.channel_tree.heading("oy", text="Off Y")
        self.channel_tree.heading("ox", text="Off X")
        self.channel_tree.column("#0", width=220, stretch=True)
        for col in ("on", "tipo", "scale", "oy", "ox"):
            self.channel_tree.column(col, width=55, stretch=False)
        self.channel_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.channel_tree.bind("<<TreeviewSelect>>", self._on_channel_select)
        self.channel_tree.bind("<Double-1>", self._toggle_selected_channel_enabled)

        edit = ttk.LabelFrame(self.tab_channels, text="Editar canal seleccionado")
        edit.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(edit, text="Visible", variable=self.channel_enabled_var, command=self._apply_channel_editor).grid(row=0, column=0, sticky="w", padx=8, pady=5)
        ttk.Button(edit, text="Cambiar color", command=self._choose_selected_color).grid(row=0, column=1, sticky="ew", padx=4, pady=5)
        ttk.Button(edit, text="Aplicar", command=self._apply_channel_editor).grid(row=0, column=2, sticky="ew", padx=4, pady=5)
        ttk.Label(edit, text="Escala Y").grid(row=1, column=0, sticky="w", padx=8)
        ttk.Entry(edit, textvariable=self.channel_scale_var).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(edit, text="Offset Y").grid(row=2, column=0, sticky="w", padx=8)
        ttk.Entry(edit, textvariable=self.channel_oy_var).grid(row=2, column=1, sticky="ew", padx=4)
        self.channel_offset_x_label = ttk.Label(edit, text="Offset X")
        self.channel_offset_x_label.grid(row=3, column=0, sticky="w", padx=8)
        self.channel_ox_entry = ttk.Entry(edit, textvariable=self.channel_ox_var)
        self.channel_ox_entry.grid(row=3, column=1, sticky="ew", padx=4)
        self.channel_ox_unit_label = ttk.Label(edit, text="µs")
        self.channel_ox_unit_label.grid(row=3, column=2, sticky="w", padx=4)
        ttk.Button(edit, text="Reset canal", command=self._reset_selected_channel).grid(row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=(7, 8))
        edit.columnconfigure(1, weight=1)
        edit.columnconfigure(2, weight=1)

    def _build_cursors_tab(self) -> None:
        ttk.Label(self.tab_cursors, text="Los cursores funcionan sobre el canal elegido. Escribís X y la Y se calcula sola.", wraplength=450).pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(self.tab_cursors, text="Agregar cursor con clic", variable=self.cursor_add_mode, command=self._toggle_cursor_add).pack(anchor="w", pady=2)
        ttk.Checkbutton(self.tab_cursors, text="Mover cursor seleccionado", variable=self.cursor_move_mode, command=self._toggle_cursor_move).pack(anchor="w", pady=2)

        row = ttk.Frame(self.tab_cursors)
        row.pack(fill=tk.X, pady=(8, 2))
        ttk.Label(row, text="Canal", width=10).grid(row=0, column=0, sticky="w")
        self.cursor_channel_menu = ttk.OptionMenu(row, self.cursor_channel_var, "")
        self.cursor_channel_menu.grid(row=0, column=1, sticky="ew", padx=4)
        row.columnconfigure(1, weight=1)

        row2 = ttk.Frame(self.tab_cursors)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="X", width=10).grid(row=0, column=0, sticky="w")
        ttk.Entry(row2, textvariable=self.cursor_x_var).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(row2, text="Y auto", width=8).grid(row=0, column=2, sticky="w")
        ttk.Label(row2, textvariable=self.cursor_y_var, relief=tk.SUNKEN, anchor="e", width=12).grid(row=0, column=3, sticky="ew", padx=4)
        row2.columnconfigure(1, weight=1)
        row2.columnconfigure(3, weight=1)

        row3 = ttk.Frame(self.tab_cursors)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="Comparar", width=10).grid(row=0, column=0, sticky="w")
        self.cursor_ref_menu = ttk.OptionMenu(row3, self.cursor_ref_var, "Ninguno")
        self.cursor_ref_menu.grid(row=0, column=1, sticky="ew", padx=4)
        row3.columnconfigure(1, weight=1)

        btns = ttk.Frame(self.tab_cursors)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Agregar", command=self._add_cursor_from_entry).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))
        ttk.Button(btns, text="Actualizar", command=self._update_selected_cursor_from_entry).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
        ttk.Button(btns, text="Borrar", command=self._delete_selected_cursor).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(3, 0))

        self.cursor_tree = ttk.Treeview(self.tab_cursors, columns=("canal", "x", "y", "dx", "dy"), show="headings", height=13)
        for col, title, width in [("canal", "Canal", 190), ("x", "X", 70), ("y", "Y", 70), ("dx", "ΔX", 70), ("dy", "ΔY", 70)]:
            self.cursor_tree.heading(col, text=title)
            self.cursor_tree.column(col, width=width, stretch=(col == "canal"))
        self.cursor_tree.pack(fill=tk.BOTH, expand=True)
        self.cursor_tree.bind("<<TreeviewSelect>>", self._on_cursor_select)

    def _entry(self, parent: ttk.Frame, label: str, var: tk.StringVar) -> ttk.Entry:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row, text=label, width=13).pack(side=tk.LEFT)
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ent.bind("<Return>", lambda _e: self.update_plot())
        return ent

    def _connect_events(self) -> None:
        self.fig.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_plot_motion)
        self.fig.canvas.mpl_connect("button_release_event", self._on_plot_release)
        self.root.bind("<Left>", lambda e: self._handle_left_right(-1, e))
        self.root.bind("<Right>", lambda e: self._handle_left_right(1, e))

    # ------------------------------------------------------------------
    # Carga de archivos
    # ------------------------------------------------------------------
    def open_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar uno o más CSV",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if paths:
            self.load_files(list(paths))

    def _on_drop(self, event) -> None:
        paths = list(self.root.tk.splitlist(event.data.strip()))
        if paths:
            self.load_files(paths)

    def load_files(self, paths: list[str]) -> None:
        csv_paths = [os.path.abspath(p) for p in paths if str(p).lower().endswith(".csv") and os.path.exists(p)]
        rejected = [os.path.basename(p) for p in paths if p not in csv_paths and not str(p).lower().endswith(".csv")]
        if not csv_paths:
            messagebox.showwarning("Sin CSV válidos", "No se recibió ningún archivo .csv válido.")
            return

        parsed: list[tuple[str, AppMode, np.ndarray, dict[str, np.ndarray], list[str]]] = []
        errors: list[str] = []
        for path in csv_paths:
            try:
                x, channels, units, mode = self._read_any_csv(path)
                if x.size == 0 or not channels:
                    raise ValueError("sin datos numéricos")
                parsed.append((path, mode, x, channels, units))
            except Exception as exc:
                errors.append(f"{os.path.basename(path)}: {exc}")

        if not parsed:
            messagebox.showerror("No se pudo leer", "No se pudo cargar ningún CSV:\n\n" + "\n".join(errors))
            return

        incoming_modes = {mode for _, mode, _, _, _ in parsed}
        if len(incoming_modes) > 1:
            messagebox.showwarning(
                "Archivos mezclados",
                "No se pueden cargar Bode y señales temporales al mismo tiempo.\n"
                "Cargá primero solo Bode o solo tiempo.",
            )
            return
        incoming_mode = incoming_modes.pop()

        if self.mode != "empty" and self.mode != incoming_mode:
            current = "Bode" if self.mode == "bode" else "tiempo"
            new = "Bode" if incoming_mode == "bode" else "tiempo"
            resp = messagebox.askyesno(
                "Cambiar modo de gráfico",
                f"Ahora estás graficando en modo {current}.\n\n"
                f"El archivo que soltaste es de modo {new}.\n\n"
                f"¿Querés borrar los datos actuales y cambiar a modo {new}?\n\n"
                "Sí = borrar actuales y cargar el nuevo.\nNo = cancelar.",
            )
            if not resp:
                self.status_var.set("Carga cancelada: se mantiene el modo actual.")
                return
            self.clear_all(ask=False)

        self.mode = incoming_mode
        for path, mode, x, ch, _units in parsed:
            stem = Path(path).stem
            for label, y in ch.items():
                kind: ChannelKind = "time"
                if mode == "bode":
                    low = label.lower()
                    kind = "bode_phase" if ("fase" in low or "phase" in low or "°" in low) else "bode_mag"
                name = self._unique_channel_name(f"{stem} - {label}")
                self.channels[name] = ChannelData(name=name, x=np.asarray(x, dtype=float), y=np.asarray(y, dtype=float), kind=kind, source_file=path)
                idx = len(self.controls)
                self.controls[name] = ChannelControls(
                    enabled=tk.BooleanVar(value=True),
                    scale_y=tk.StringVar(value="1"),
                    offset_y=tk.StringVar(value="0"),
                    offset_x=tk.StringVar(value="0"),
                    color=tk.StringVar(value=DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]),
                )
            if path not in self.loaded_files:
                self.loaded_files.append(path)

        self._sync_after_data_change()
        added = sum(len(ch) for _, _, _, ch, _ in parsed)
        self.status_var.set(f"Cargados {added} canal(es) en modo {'Bode' if self.mode == 'bode' else 'tiempo'}.")
        if errors or rejected:
            messagebox.showwarning("Algunos archivos se omitieron", "\n".join(errors + rejected))

    def _unique_channel_name(self, base: str) -> str:
        if base not in self.channels:
            return base
        i = 2
        while f"{base} ({i})" in self.channels:
            i += 1
        return f"{base} ({i})"

    def _detect_delimiter(self, path: str) -> str:
        with open(path, "r", newline="", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        except Exception:
            return ","

    def _read_any_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str], AppMode]:
        if self._looks_like_ltspice_bode(path):
            x, ch, units = self._read_ltspice_bode(path)
            return x, ch, units, "bode"
        if self._looks_like_named_bode(path):
            x, ch, units = self._read_named_bode(path)
            return x, ch, units, "bode"
        x, ch, units = self._read_time_csv(path)
        return x, ch, units, "time"

    def _looks_like_named_bode(self, path: str) -> bool:
        sep = self._detect_delimiter(path)
        try:
            df = pd.read_csv(path, sep=sep, nrows=10, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        except Exception:
            return False
        cols = [str(c).lower().strip() for c in df.columns]
        has_f = any("freq" in c or "frecuencia" in c for c in cols)
        has_mag = any("db" in c or "gain" in c or "magnitud" in c for c in cols)
        has_phase = any("phase" in c or "fase" in c for c in cols)
        return has_f and (has_mag or has_phase)

    def _read_named_bode(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        sep = self._detect_delimiter(path)
        df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        cols = list(df.columns)
        low = [str(c).lower().strip() for c in cols]

        def find(pred):
            for c, l in zip(cols, low):
                if pred(l):
                    return c
            return None

        freq_col = find(lambda c: "freq" in c or "frecuencia" in c)
        gain_col = find(lambda c: "db" in c or "gain" in c or "magnitud" in c)
        phase_col = find(lambda c: "phase" in c or "fase" in c)
        if freq_col is None:
            raise ValueError("no se encontró columna de frecuencia")
        freq = pd.to_numeric(df[freq_col], errors="coerce").to_numpy(float)
        channels: dict[str, np.ndarray] = {}
        if gain_col is not None:
            channels["Ganancia [dB]"] = pd.to_numeric(df[gain_col], errors="coerce").to_numpy(float)
        if phase_col is not None:
            channels["Fase [°]"] = pd.to_numeric(df[phase_col], errors="coerce").to_numpy(float)
        return freq, channels, ["Hz", "dB", "°"]

    def _looks_like_ltspice_bode(self, path: str) -> bool:
        sep = self._detect_delimiter(path)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                header = f.readline().strip()
                first_data = f.readline().strip()
        except Exception:
            return False
        first_col = (re.split(rf"{re.escape(sep)}", header)[0] if header else "").lower()
        return first_col.startswith("freq") and "(" in first_data and "db" in first_data.lower()

    def _parse_bode_cell(self, value) -> tuple[float, float]:
        text = str(value).strip().strip('"').strip("'").strip().strip("()")
        parts = [p.strip() for p in text.split(",")]
        mag = float(parts[0].lower().replace("db", "").strip())
        phase = float(parts[1].replace("°", "").strip()) if len(parts) > 1 and parts[1] else np.nan
        return mag, phase

    def _read_ltspice_bode(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        sep = self._detect_delimiter(path)
        df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        if df.shape[1] < 2:
            raise ValueError("Bode con menos de dos columnas")
        freq = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(float)
        channels: dict[str, np.ndarray] = {}
        for col in df.columns[1:]:
            mags, phases = [], []
            for cell in df[col]:
                try:
                    mag, ph = self._parse_bode_cell(cell)
                except Exception:
                    mag, ph = np.nan, np.nan
                mags.append(mag)
                phases.append(ph)
            base = str(col).strip()
            channels[f"{base} - Ganancia [dB]"] = np.asarray(mags, dtype=float)
            channels[f"{base} - Fase [°]"] = np.asarray(phases, dtype=float)
        return freq, channels, ["Hz", "dB", "°"]

    def _read_time_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        sep = self._detect_delimiter(path)
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            first_lines = [f.readline().strip() for _ in range(3)]
        first = re.split(rf"{re.escape(sep)}", first_lines[0]) if first_lines[0] else []
        second = re.split(rf"{re.escape(sep)}", first_lines[1]) if first_lines[1] else []
        looks_like_scope = bool(first) and first[0].strip().lower() in {"x-axis", "time", "tiempo"}
        if looks_like_scope:
            names = [c.strip() for c in first]
            units = [c.strip() for c in second]
            df = pd.read_csv(path, sep=sep, skiprows=2, header=None, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
            numeric = df.apply(pd.to_numeric, errors="coerce").dropna(how="all").dropna(axis=1, how="all")
            if numeric.shape[1] < 2:
                raise ValueError("menos de dos columnas numéricas")
            x = numeric.iloc[:, 0].to_numpy(float)
            channels = {}
            for i in range(1, numeric.shape[1]):
                label = names[i] if i < len(names) and names[i] else f"Canal {i}"
                if label.isdigit():
                    label = f"Canal {label}"
                channels[label] = numeric.iloc[:, i].to_numpy(float)
            return x, channels, units
        try:
            df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
            numeric = df.apply(pd.to_numeric, errors="coerce")
            if numeric.shape[1] < 2 or numeric.dropna(how="all").empty:
                raise ValueError
            labels = list(df.columns)
        except Exception:
            df = pd.read_csv(path, sep=sep, header=None, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
            numeric = df.apply(pd.to_numeric, errors="coerce")
            labels = [f"Columna {i+1}" for i in range(numeric.shape[1])]
        numeric = numeric.dropna(how="all").dropna(axis=1, how="all")
        if numeric.shape[1] < 2:
            raise ValueError("menos de dos columnas numéricas")
        x = numeric.iloc[:, 0].to_numpy(float)
        channels = {
            str(labels[i]) if i < len(labels) else f"Canal {i}": numeric.iloc[:, i].to_numpy(float)
            for i in range(1, numeric.shape[1])
        }
        return x, channels, []

    # ------------------------------------------------------------------
    # Sincronización UI
    # ------------------------------------------------------------------
    def _sync_after_data_change(self) -> None:
        self._update_mode_labels()
        self._refresh_channel_tree()
        self._rebuild_channel_menus()
        self._refresh_cursor_tree()
        self.update_plot()

    def _update_mode_labels(self) -> None:
        label = {"empty": "Modo: vacío", "time": "Modo: tiempo", "bode": "Modo: Bode"}[self.mode]
        self.mode_var.set(label)
        if not self.loaded_files:
            self.file_label.config(text="Sin archivos cargados")
        elif len(self.loaded_files) == 1:
            self.file_label.config(text=os.path.basename(self.loaded_files[0]))
        else:
            self.file_label.config(text=f"{len(self.loaded_files)} CSV cargados")

        self.shift_x_unit_label.config(text=self.x_unit_var.get())
        self.channel_ox_unit_label.config(text=self.x_unit_var.get())
        self._set_mode_widgets()

    def _set_mode_widgets(self) -> None:
        # Evita mostrar herramientas de tiempo cuando se trabaja con Bode.
        if self.mode == "bode":
            self.time_options.pack_forget()
            self.shift_box.pack_forget()
            if not self.bode_options.winfo_ismapped():
                self.bode_options.pack(fill=tk.X, pady=(0, 8), before=self.tab_plot.winfo_children()[-1])
            self.time_logx_check.state(["disabled"])
            self.time_logy_check.state(["disabled"])
            self.log_x_var.set(False)
            self.log_y_var.set(False)
            self.xy_mode_var.set(False)
            self.shift_mode_var.set(False)
            self.channel_offset_x_label.grid_remove()
            self.channel_ox_entry.grid_remove()
            self.channel_ox_unit_label.grid_remove()
        elif self.mode == "time":
            self.bode_options.pack_forget()
            if not self.time_options.winfo_ismapped():
                self.time_options.pack(fill=tk.X, pady=(0, 8), after=self.tab_plot.winfo_children()[0])
            if not self.shift_box.winfo_ismapped():
                self.shift_box.pack(fill=tk.X, pady=(0, 8), after=self.time_options)
            self.time_logx_check.state(["!disabled"])
            self.time_logy_check.state(["!disabled"])
            self.channel_offset_x_label.grid()
            self.channel_ox_entry.grid()
            self.channel_ox_unit_label.grid()
        else:
            # Pantalla vacía: muestra lo general y modo tiempo por defecto.
            self.bode_options.pack_forget()
            if not self.time_options.winfo_ismapped():
                self.time_options.pack(fill=tk.X, pady=(0, 8), after=self.tab_plot.winfo_children()[0])
            if not self.shift_box.winfo_ismapped():
                self.shift_box.pack(fill=tk.X, pady=(0, 8), after=self.time_options)
            self.time_logx_check.state(["!disabled"])
            self.time_logy_check.state(["!disabled"])
            self.channel_offset_x_label.grid()
            self.channel_ox_entry.grid()
            self.channel_ox_unit_label.grid()

    def _refresh_channel_tree(self) -> None:
        for item in self.channel_tree.get_children():
            self.channel_tree.delete(item)
        for name, data in self.channels.items():
            ctrl = self.controls[name]
            tipo = {"time": "Tiempo", "bode_mag": "Bode dB", "bode_phase": "Bode °"}[data.kind]
            on = "✓" if ctrl.enabled.get() else "—"
            ox = ctrl.offset_x.get() if data.kind == "time" else ""
            self.channel_tree.insert("", "end", iid=name, text=name, values=(on, tipo, ctrl.scale_y.get(), ctrl.offset_y.get(), ox))

    def _rebuild_channel_menus(self) -> None:
        names = list(self.channels.keys())
        time_names = [n for n in names if self.channels[n].kind == "time"]
        cursor_names = time_names if self.mode == "time" else names if self.mode == "bode" else []

        self._rebuild_menu(self.shift_channel_menu, self.shift_channel_var, time_names, self._on_shift_channel_changed)
        self._rebuild_menu(self.cursor_channel_menu, self.cursor_channel_var, cursor_names, None)
        self._rebuild_menu(self.xy_x_menu, self.xy_x_var, time_names, lambda: self.update_plot())
        self._rebuild_menu(self.xy_y_menu, self.xy_y_var, time_names, lambda: self.update_plot())

        if len(time_names) >= 2:
            if self.xy_x_var.get() not in time_names:
                self.xy_x_var.set(time_names[0])
            if self.xy_y_var.get() not in time_names:
                self.xy_y_var.set(time_names[1])
        elif len(time_names) == 1:
            self.xy_x_var.set(time_names[0])
            self.xy_y_var.set(time_names[0])
        else:
            self.xy_x_var.set("")
            self.xy_y_var.set("")

    def _rebuild_menu(self, widget: ttk.OptionMenu, var: tk.StringVar, values: list[str], callback=None) -> None:
        menu = widget["menu"]
        menu.delete(0, "end")
        if values and var.get() not in values:
            var.set(values[0])
        elif not values:
            var.set("")
        for value in values:
            menu.add_command(label=value, command=lambda v=value: (var.set(v), callback() if callback else None))

    def _on_channel_select(self, _event=None) -> None:
        selected = self.channel_tree.selection()
        if not selected:
            return
        name = selected[0]
        if name not in self.controls:
            return
        ctrl = self.controls[name]
        self.channel_enabled_var.set(ctrl.enabled.get())
        self.channel_scale_var.set(ctrl.scale_y.get())
        self.channel_oy_var.set(ctrl.offset_y.get())
        self.channel_ox_var.set(ctrl.offset_x.get())
        if self.channels[name].kind == "time":
            self.shift_channel_var.set(name)
            self.shift_x_var.set(ctrl.offset_x.get())

    def _apply_channel_editor(self) -> None:
        selected = self.channel_tree.selection()
        if not selected:
            messagebox.showinfo("Canal", "Seleccioná un canal de la tabla.")
            return
        name = selected[0]
        ctrl = self.controls.get(name)
        if not ctrl:
            return
        ctrl.enabled.set(self.channel_enabled_var.get())
        ctrl.scale_y.set(self.channel_scale_var.get())
        ctrl.offset_y.set(self.channel_oy_var.get())
        if self.channels[name].kind == "time":
            ctrl.offset_x.set(self.channel_ox_var.get())
        self._refresh_channel_tree()
        self.update_plot()

    def _reset_selected_channel(self) -> None:
        selected = self.channel_tree.selection()
        if not selected:
            return
        name = selected[0]
        ctrl = self.controls[name]
        ctrl.scale_y.set("1")
        ctrl.offset_y.set("0")
        ctrl.offset_x.set("0")
        self._on_channel_select()
        self._refresh_channel_tree()
        self.update_plot()

    def _toggle_selected_channel_enabled(self, _event=None) -> None:
        selected = self.channel_tree.selection()
        if not selected:
            return
        name = selected[0]
        ctrl = self.controls.get(name)
        if ctrl:
            ctrl.enabled.set(not ctrl.enabled.get())
            self.channel_enabled_var.set(ctrl.enabled.get())
            self._refresh_channel_tree()
            self.update_plot()

    def _choose_selected_color(self) -> None:
        selected = self.channel_tree.selection()
        if not selected:
            messagebox.showinfo("Color", "Seleccioná un canal de la tabla.")
            return
        name = selected[0]
        ctrl = self.controls[name]
        # colorchooser de Tkinter no acepta colores de Matplotlib como "tab:blue".
        # Usamos un color inicial seguro si quedó algún color viejo guardado.
        initial_color = ctrl.color.get()
        if not str(initial_color).startswith("#"):
            initial_color = "#1f77b4"
        chosen = colorchooser.askcolor(color=initial_color, title=f"Color para {name}")
        if chosen and chosen[1]:
            ctrl.color.set(chosen[1])
            # También actualiza cursores que pertenecen a ese canal.
            for cursor in self.cursors:
                if cursor.channel == name:
                    cursor.color = chosen[1]
            self._refresh_channel_tree()
            self._refresh_cursor_tree()
            self.update_plot()
            self.status_var.set(f"Color actualizado para {name}")

    def _on_shift_channel_changed(self) -> None:
        name = self.shift_channel_var.get()
        if name in self.controls:
            self.shift_x_var.set(self.controls[name].offset_x.get())

    # ------------------------------------------------------------------
    # Transformaciones y gráficos
    # ------------------------------------------------------------------
    def _safe_float(self, text: str, default: float = 0.0) -> float:
        try:
            text = str(text).replace(",", ".").strip()
            return float(text) if text else default
        except Exception:
            return default

    def _x_display(self, name: str) -> np.ndarray:
        data = self.channels[name]
        ctrl = self.controls[name]
        x = np.asarray(data.x, dtype=float).copy()
        if data.kind == "time":
            finite = np.isfinite(x)
            if self.align_time_var.get() and finite.any():
                x = x - x[finite][0]
            x = x * X_UNITS.get(self.x_unit_var.get(), 1.0)
            x = x + self._safe_float(ctrl.offset_x.get(), 0.0)
        return x

    def _y_display(self, name: str) -> np.ndarray:
        data = self.channels[name]
        ctrl = self.controls[name]
        y = np.asarray(data.y, dtype=float)
        y = y * self._safe_float(ctrl.scale_y.get(), 1.0) + self._safe_float(ctrl.offset_y.get(), 0.0)
        if data.kind == "time":
            y = y * Y_UNITS.get(self.y_unit_var.get(), 1.0)
        return y

    def update_plot(self) -> None:
        self.fig.clear()
        self.bode_axes = {}
        if not self.channels:
            self._plot_empty(draw=False)
            self.canvas.draw_idle()
            return
        if self.mode == "bode":
            self._plot_bode()
        elif self.xy_mode_var.get():
            self._plot_xy()
        else:
            self._plot_time()
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _plot_empty(self, draw: bool = True) -> None:
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.text(0.5, 0.5, "Cargá o arrastrá uno o más CSV", ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_axis_off()
        if draw:
            self.canvas.draw_idle()

    def _plot_time(self) -> None:
        self.ax = self.fig.add_subplot(111)
        plotted = False
        for name, data in self.channels.items():
            ctrl = self.controls[name]
            if not ctrl.enabled.get() or data.kind != "time":
                continue
            x = self._x_display(name)
            y = self._y_display(name)
            self.ax.plot(x, y, label=name, color=ctrl.color.get())
            self._mark_points(self.ax, x, y, name, ctrl.color.get())
            plotted = True
        self.ax.set_title(self.title_var.get())
        self.ax.set_xlabel(f"{self.xlabel_var.get()} [{self.x_unit_var.get()}]")
        self.ax.set_ylabel(f"{self.ylabel_var.get()} [{self.y_unit_var.get()}]")
        self._apply_grid_and_scales(self.ax)
        if plotted:
            self.ax.legend(loc="best")
        self._redraw_cursors()

    def _plot_bode(self) -> None:
        ax_mag = self.fig.add_subplot(211)
        ax_phase = self.fig.add_subplot(212, sharex=ax_mag)
        self.ax = ax_mag
        self.bode_axes = {"bode_mag": ax_mag, "bode_phase": ax_phase}
        mag_count = 0
        phase_count = 0
        for name, data in self.channels.items():
            ctrl = self.controls[name]
            if not ctrl.enabled.get():
                continue
            x = self._x_display(name)
            y = self._y_display(name)
            finite = np.isfinite(x) & np.isfinite(y) & (x > 0)
            if not finite.any():
                continue
            if data.kind == "bode_phase":
                ax_phase.semilogx(x[finite], y[finite], label=name, color=ctrl.color.get())
                phase_count += 1
            elif data.kind == "bode_mag":
                ax_mag.semilogx(x[finite], y[finite], label=name, color=ctrl.color.get())
                mag_count += 1
        ax_mag.set_title(self.title_var.get() if self.title_var.get() else "Diagrama de Bode")
        ax_mag.set_ylabel("Magnitud [dB]")
        ax_phase.set_ylabel("Fase [°]")
        ax_phase.set_xlabel("Frecuencia [Hz]")
        if self.grid_var.get():
            ax_mag.grid(True, which="both", alpha=0.35)
            ax_phase.grid(True, which="both", alpha=0.35)
        if mag_count:
            ax_mag.legend(loc="best")
        else:
            ax_mag.text(0.5, 0.5, "No hay magnitud activa", ha="center", va="center", transform=ax_mag.transAxes)
        if phase_count:
            ax_phase.legend(loc="best")
        else:
            ax_phase.text(0.5, 0.5, "No hay fase activa", ha="center", va="center", transform=ax_phase.transAxes)
        self._redraw_cursors()

    def _plot_xy(self) -> None:
        self.ax = self.fig.add_subplot(111)
        x_name = self.xy_x_var.get()
        y_name = self.xy_y_var.get()
        if x_name not in self.channels or y_name not in self.channels:
            self.ax.text(0.5, 0.5, "Elegí dos canales temporales válidos", ha="center", va="center", transform=self.ax.transAxes)
            return
        x_data = self._y_display(x_name)
        y_data = self._y_display(y_name)
        tx = self._x_display(x_name)
        ty = self._x_display(y_name)
        if len(x_data) != len(y_data) or not np.array_equal(tx, ty):
            finite_y = np.isfinite(ty) & np.isfinite(y_data)
            finite_x = np.isfinite(tx) & np.isfinite(x_data)
            if not finite_x.any() or not finite_y.any():
                return
            order = np.argsort(ty[finite_y])
            y_interp = np.interp(tx[finite_x], ty[finite_y][order], y_data[finite_y][order])
            x_plot = x_data[finite_x]
            y_plot = y_interp
        else:
            x_plot, y_plot = x_data, y_data
        color = self.controls[y_name].color.get()
        self.ax.plot(x_plot, y_plot, label=f"{y_name} vs {x_name}", color=color)
        self.ax.set_title("Modo XY / Lissajous")
        self.ax.set_xlabel(f"{x_name} [{self.y_unit_var.get()}]")
        self.ax.set_ylabel(f"{y_name} [{self.y_unit_var.get()}]")
        self._apply_grid_and_scales(self.ax)
        self.ax.legend(loc="best")

    def _apply_grid_and_scales(self, ax) -> None:
        if self.log_x_var.get():
            ax.set_xscale("log")
        if self.log_y_var.get():
            ax.set_yscale("log")
        if self.grid_var.get():
            ax.grid(True, which="both", alpha=0.35)
            x_step = self._safe_float(self.grid_x_step_var.get(), 0.0)
            y_step = self._safe_float(self.grid_y_step_var.get(), 0.0)
            if x_step > 0 and not self.log_x_var.get():
                ax.xaxis.set_major_locator(MultipleLocator(x_step))
            if y_step > 0 and not self.log_y_var.get():
                ax.yaxis.set_major_locator(MultipleLocator(y_step))
        else:
            ax.grid(False)

    def _mark_points(self, ax, x: np.ndarray, y: np.ndarray, name: str, color: str) -> None:
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            return
        xf, yf = x[finite], y[finite]
        if self.mark_max_var.get():
            idx = int(np.argmax(yf))
            ax.scatter([xf[idx]], [yf[idx]], color=color, marker="o")
            ax.annotate(f"max {name}\n({xf[idx]:.4g}, {yf[idx]:.4g})", (xf[idx], yf[idx]), textcoords="offset points", xytext=(8, 8), fontsize=8)
        if self.mark_min_var.get():
            idx = int(np.argmin(yf))
            ax.scatter([xf[idx]], [yf[idx]], color=color, marker="v")
            ax.annotate(f"min {name}\n({xf[idx]:.4g}, {yf[idx]:.4g})", (xf[idx], yf[idx]), textcoords="offset points", xytext=(8, -16), fontsize=8)

    # ------------------------------------------------------------------
    # Cursores
    # ------------------------------------------------------------------
    def _toggle_cursor_add(self) -> None:
        if self.cursor_add_mode.get():
            self.cursor_move_mode.set(False)
            self.shift_mode_var.set(False)
            if self.mode == "bode":
                self.status_var.set("Cursores Bode: elegí magnitud o fase y hacé clic. La Y se calcula sola.")
            else:
                self.status_var.set("Cursores: elegí un canal y hacé clic para agregar. La Y se calcula sola.")

    def _toggle_cursor_move(self) -> None:
        if self.cursor_move_mode.get():
            self.cursor_add_mode.set(False)
            self.shift_mode_var.set(False)
            self.status_var.set("Mover cursor: seleccioná uno y movelo con mouse o flechas.")

    def _on_plot_click(self, event) -> None:
        if event.xdata is None:
            return
        if self.xy_mode_var.get() and self.mode == "time":
            return
        if self.shift_mode_var.get() and self.mode == "time":
            if event.inaxes != getattr(self, "ax", None):
                return
            self.dragging_channel_shift = True
            self.last_shift_x = float(event.xdata)
            return
        if self.cursor_move_mode.get():
            cur = self._selected_cursor()
            if cur is None:
                messagebox.showwarning("Sin cursor", "Seleccioná un cursor de la tabla.")
                return
            if self._event_matches_cursor_axis(event, cur.channel):
                self.dragging_cursor = True
                self._move_cursor_to_x(cur, float(event.xdata))
            return
        if self.cursor_add_mode.get():
            ch = self.cursor_channel_var.get()
            if ch not in self.channels:
                return
            if self._event_matches_cursor_axis(event, ch):
                self._add_cursor(ch, float(event.xdata))

    def _event_matches_cursor_axis(self, event, channel: str) -> bool:
        if channel not in self.channels:
            return False
        if self.mode == "time":
            return event.inaxes == getattr(self, "ax", None)
        if self.mode == "bode":
            kind = self.channels[channel].kind
            return event.inaxes == self.bode_axes.get(kind)
        return False

    def _on_plot_motion(self, event) -> None:
        if event.xdata is None:
            return
        if self.dragging_channel_shift and self.shift_mode_var.get() and self.last_shift_x is not None and self.mode == "time":
            if event.inaxes != getattr(self, "ax", None):
                return
            name = self.shift_channel_var.get()
            dx = float(event.xdata) - self.last_shift_x
            self.last_shift_x = float(event.xdata)
            self._shift_channel_by(name, dx)
            return
        if self.dragging_cursor and self.cursor_move_mode.get():
            cur = self._selected_cursor()
            if cur and self._event_matches_cursor_axis(event, cur.channel):
                self._move_cursor_to_x(cur, float(event.xdata))

    def _on_plot_release(self, _event) -> None:
        self.dragging_cursor = False
        self.dragging_channel_shift = False
        self.last_shift_x = None

    def _interp_channel_y(self, channel: str, x_val: float) -> float:
        if channel not in self.channels:
            return 0.0
        x = self._x_display(channel)
        y = self._y_display(channel)
        finite = np.isfinite(x) & np.isfinite(y)
        if not finite.any():
            return 0.0
        xf, yf = x[finite], y[finite]
        order = np.argsort(xf)
        return float(np.interp(x_val, xf[order], yf[order]))

    def _add_cursor(self, channel: str, x: float) -> None:
        y = self._interp_channel_y(channel, x)
        color = self.controls[channel].color.get()
        cursor = CursorItem(self.next_cursor_id, channel, x, y, color)
        self.next_cursor_id += 1
        self.cursors.append(cursor)
        self.selected_cursor_id = cursor.cursor_id
        self.cursor_x_var.set(f"{x:.8g}")
        self.cursor_y_var.set(f"{y:.8g}")
        self._refresh_cursor_tree()
        self.update_plot()

    def _add_cursor_from_entry(self) -> None:
        ch = self.cursor_channel_var.get()
        if ch not in self.channels:
            messagebox.showwarning("Canal", "Elegí un canal válido.")
            return
        try:
            x = float(self.cursor_x_var.get().replace(",", "."))
        except Exception:
            messagebox.showwarning("X inválida", "Escribí una X numérica.")
            return
        self._add_cursor(ch, x)

    def _selected_cursor(self) -> Optional[CursorItem]:
        if self.selected_cursor_id is None:
            return None
        for c in self.cursors:
            if c.cursor_id == self.selected_cursor_id:
                return c
        return None

    def _update_selected_cursor_from_entry(self) -> None:
        cur = self._selected_cursor()
        if cur is None:
            messagebox.showwarning("Cursor", "Seleccioná un cursor.")
            return
        ch = self.cursor_channel_var.get()
        if ch not in self.channels:
            return
        try:
            x = float(self.cursor_x_var.get().replace(",", "."))
        except Exception:
            messagebox.showwarning("X inválida", "Escribí una X numérica.")
            return
        cur.channel = ch
        cur.color = self.controls[ch].color.get()
        self._move_cursor_to_x(cur, x)

    def _move_cursor_to_x(self, cur: CursorItem, x: float) -> None:
        cur.x = x
        cur.y = self._interp_channel_y(cur.channel, x)
        cur.color = self.controls[cur.channel].color.get()
        self.selected_cursor_id = cur.cursor_id
        self.cursor_channel_var.set(cur.channel)
        self.cursor_x_var.set(f"{cur.x:.8g}")
        self.cursor_y_var.set(f"{cur.y:.8g}")
        self._refresh_cursor_tree()
        self.update_plot()

    def _move_selected_cursor_by_key(self, direction: int) -> None:
        if not self.cursor_move_mode.get():
            return
        cur = self._selected_cursor()
        if not cur:
            return
        x = self._x_display(cur.channel)
        finite = np.isfinite(x)
        if finite.sum() < 2:
            return
        xs = np.sort(np.unique(x[finite]))
        idx = int(np.searchsorted(xs, cur.x))
        idx = max(0, min(len(xs) - 1, idx + direction))
        self._move_cursor_to_x(cur, float(xs[idx]))

    def _delete_selected_cursor(self) -> None:
        cur = self._selected_cursor()
        if cur is None:
            return
        self.cursors = [c for c in self.cursors if c.cursor_id != cur.cursor_id]
        self.selected_cursor_id = None
        self.cursor_x_var.set("")
        self.cursor_y_var.set("")
        self._refresh_cursor_tree()
        self.update_plot()

    def _on_cursor_select(self, _event=None) -> None:
        sel = self.cursor_tree.selection()
        if not sel:
            return
        try:
            cid = int(sel[0])
        except Exception:
            return
        for c in self.cursors:
            if c.cursor_id == cid:
                self.selected_cursor_id = cid
                self.cursor_channel_var.set(c.channel)
                self.cursor_x_var.set(f"{c.x:.8g}")
                self.cursor_y_var.set(f"{c.y:.8g}")
                return

    def _refresh_cursor_tree(self) -> None:
        if not hasattr(self, "cursor_tree"):
            return
        self._rebuild_cursor_ref_menu()
        for item in self.cursor_tree.get_children():
            self.cursor_tree.delete(item)
        ref = self._cursor_by_ref()
        for c in self.cursors:
            dx = dy = "-"
            if ref is not None and ref.cursor_id != c.cursor_id:
                dx = f"{c.x - ref.x:.5g}"
                dy = f"{c.y - ref.y:.5g}"
            self.cursor_tree.insert("", "end", iid=str(c.cursor_id), values=(c.channel, f"{c.x:.5g}", f"{c.y:.5g}", dx, dy))
        if self.selected_cursor_id is not None and self.cursor_tree.exists(str(self.selected_cursor_id)):
            self.cursor_tree.selection_set(str(self.selected_cursor_id))

    def _rebuild_cursor_ref_menu(self) -> None:
        values = ["Ninguno"] + [f"C{c.cursor_id} - {c.channel}" for c in self.cursors]
        if self.cursor_ref_var.get() not in values:
            self.cursor_ref_var.set("Ninguno")
        menu = self.cursor_ref_menu["menu"]
        menu.delete(0, "end")
        for v in values:
            menu.add_command(label=v, command=lambda val=v: (self.cursor_ref_var.set(val), self._refresh_cursor_tree()))

    def _cursor_by_ref(self) -> Optional[CursorItem]:
        m = re.match(r"C(\d+)", self.cursor_ref_var.get())
        if not m:
            return None
        cid = int(m.group(1))
        for c in self.cursors:
            if c.cursor_id == cid:
                return c
        return None

    def _redraw_cursors(self) -> None:
        if self.mode == "time":
            if self.xy_mode_var.get():
                return
            for c in self.cursors:
                if c.channel not in self.channels or self.channels[c.channel].kind != "time":
                    continue
                self._draw_cursor_on_axis(self.ax, c)
        elif self.mode == "bode":
            for c in self.cursors:
                if c.channel not in self.channels:
                    continue
                kind = self.channels[c.channel].kind
                ax = self.bode_axes.get(kind)
                if ax is not None:
                    self._draw_cursor_on_axis(ax, c)

    def _draw_cursor_on_axis(self, ax, cursor: CursorItem) -> None:
        selected = cursor.cursor_id == self.selected_cursor_id
        lw = 2.0 if selected else 1.2
        size = 65 if selected else 35
        ax.axvline(cursor.x, linestyle="--", linewidth=lw, color=cursor.color, alpha=0.85)
        ax.axhline(cursor.y, linestyle=":", linewidth=lw, color=cursor.color, alpha=0.85)
        ax.scatter([cursor.x], [cursor.y], color=cursor.color, s=size, zorder=5)
        ax.annotate(f"C{cursor.cursor_id}\n{cursor.channel}", (cursor.x, cursor.y), textcoords="offset points", xytext=(7, 7), fontsize=8, color=cursor.color)

    # ------------------------------------------------------------------
    # Ajuste temporal / fase
    # ------------------------------------------------------------------
    def _toggle_shift_mode(self) -> None:
        if self.mode != "time" and self.shift_mode_var.get():
            self.shift_mode_var.set(False)
            return
        if self.shift_mode_var.get():
            self.cursor_add_mode.set(False)
            self.cursor_move_mode.set(False)
            self.status_var.set("Ajuste X activo: arrastrá el canal seleccionado o usá flechas.")
        else:
            self.dragging_channel_shift = False
            self.last_shift_x = None
            self.status_var.set("Ajuste X desactivado.")

    def _apply_shift_entry(self) -> None:
        name = self.shift_channel_var.get()
        if name not in self.controls or self.channels[name].kind != "time":
            messagebox.showinfo("Ajuste X", "Seleccioná un canal temporal.")
            return
        self.controls[name].offset_x.set(self.shift_x_var.get())
        self._refresh_channel_tree()
        self.update_plot()

    def _shift_channel_by(self, name: str, dx: float) -> None:
        if name not in self.controls or self.channels[name].kind != "time":
            return
        ctrl = self.controls[name]
        new_val = self._safe_float(ctrl.offset_x.get(), 0.0) + dx
        ctrl.offset_x.set(f"{new_val:.8g}")
        self.shift_x_var.set(ctrl.offset_x.get())
        self._refresh_channel_tree()
        self.update_plot()
        self.status_var.set(f"{name}: Offset X = {new_val:.8g} {self.x_unit_var.get()}")

    def _x_step_for_channel(self, name: str) -> float:
        if name not in self.channels:
            return 1.0
        x = self._x_display(name)
        finite = np.isfinite(x)
        if finite.sum() < 2:
            return 1.0
        xs = np.sort(np.unique(x[finite]))
        diffs = np.diff(xs)
        diffs = diffs[diffs > 0]
        return float(np.median(diffs)) if diffs.size else 1.0

    def _handle_left_right(self, direction: int, event=None):
        if self.shift_mode_var.get() and self.mode == "time":
            name = self.shift_channel_var.get()
            if name in self.channels:
                step = self._x_step_for_channel(name)
                state = getattr(event, "state", 0) if event is not None else 0
                if state & 0x0001:
                    step *= 10
                if state & 0x0004:
                    step *= 0.1
                self._shift_channel_by(name, direction * step)
            return "break"
        self._move_selected_cursor_by_key(direction)
        return "break"

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------
    def export_pdf(self) -> None:
        if not self.channels:
            messagebox.showinfo("Guardar PDF", "Primero cargá algún CSV para poder exportar el gráfico.")
            return

        if self.mode == "bode":
            default_name = "bode_tc1.pdf"
        elif self.xy_mode_var.get():
            default_name = "xy_tc1.pdf"
        elif self.loaded_files:
            default_name = f"{Path(self.loaded_files[0]).stem}_grafico.pdf"
        else:
            default_name = "grafico_tc1.pdf"

        out_path = filedialog.asksaveasfilename(
            title="Guardar gráfico como PDF",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF", "*.pdf"), ("Todos los archivos", "*.*")],
        )
        if not out_path:
            return

        old_size = tuple(self.fig.get_size_inches())
        try:
            self.fig.set_size_inches(11.0, 8.0 if self.mode == "bode" else 6.8)
            self.update_plot()
            mode_text = {"empty": "Vacío", "time": "Tiempo", "bode": "Bode"}.get(self.mode, self.mode)
            visible = [name for name, ctrl in self.controls.items() if ctrl.enabled.get()]
            footer_parts = [f"Modo: {mode_text}"]
            if self.loaded_files:
                footer_parts.append("Archivos: " + ", ".join(Path(p).name for p in self.loaded_files[:3]))
                if len(self.loaded_files) > 3:
                    footer_parts.append(f"+{len(self.loaded_files)-3} más")
            footer_parts.append(f"Canales visibles: {len(visible)}")
            footer_parts.append(datetime.now().strftime("Exportado: %d/%m/%Y %H:%M"))
            footer = "   |   ".join(footer_parts)
            self.fig.text(0.5, 0.012, footer, ha="center", va="bottom", fontsize=8, color="#555555")
            self.fig.subplots_adjust(bottom=0.10)
            self.fig.savefig(out_path, format="pdf", bbox_inches="tight", facecolor="white", edgecolor="none")
            self.status_var.set(f"PDF guardado: {out_path}")
            messagebox.showinfo("PDF guardado", f"Se guardó el gráfico en:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Error al guardar PDF", f"No se pudo guardar el PDF.\n\nDetalle: {exc}")
        finally:
            self.fig.set_size_inches(*old_size)
            self.update_plot()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    def _toggle_xy(self) -> None:
        if self.mode == "bode" and self.xy_mode_var.get():
            messagebox.showinfo("Modo XY", "El modo XY solo aplica a señales temporales.")
            self.xy_mode_var.set(False)
            return
        self.update_plot()

    def _unit_changed(self) -> None:
        self._update_mode_labels()
        self._refresh_channel_tree()
        self.update_plot()

    def clear_all(self, ask: bool = True) -> None:
        if ask and self.channels:
            if not messagebox.askyesno("Limpiar todo", "¿Seguro que querés borrar todos los canales y cursores cargados?"):
                return
        self.mode = "empty"
        self.channels.clear()
        self.controls.clear()
        self.loaded_files.clear()
        self.cursors.clear()
        self.selected_cursor_id = None
        self.cursor_x_var.set("")
        self.cursor_y_var.set("")
        self.shift_x_var.set("0")
        self.xy_mode_var.set(False)
        self.shift_mode_var.set(False)
        self.cursor_add_mode.set(False)
        self.cursor_move_mode.set(False)
        self._sync_after_data_change()
        self.status_var.set("Cargá o arrastrá uno o más CSV")


def main() -> None:
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    TC1CSVGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
