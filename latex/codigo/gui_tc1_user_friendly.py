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
    x_offset: tk.StringVar
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
        self.file_paths: list[str] = []
        self.raw_df: Optional[pd.DataFrame] = None
        self.units_row: list[str] = []
        self.time: Optional[np.ndarray] = None
        self.channel_times: dict[str, np.ndarray] = {}
        self.channel_kinds: dict[str, str] = {}  # 'time', 'bode_mag' o 'bode_phase'
        self.channels: dict[str, np.ndarray] = {}
        self.controls: dict[str, ChannelControls] = {}

        self.cursor_mode = tk.BooleanVar(value=False)
        self.move_cursor_mode = tk.BooleanVar(value=False)
        self.shift_channel_mode = tk.BooleanVar(value=False)
        self.dragging_cursor = False
        self.dragging_channel_shift = False
        self.last_shift_x: Optional[float] = None
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
        self.align_time_var = tk.BooleanVar(value=True)
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
        self.shift_channel_var = tk.StringVar(value="")
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

        ttk.Button(file_box, text="Agregar CSV", command=self.open_file).pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(file_box, text="Limpiar todo", command=self.clear_all_files).pack(fill=tk.X, padx=8, pady=(0, 6))
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
        ttk.Checkbutton(grid_box, text="Alinear cada CSV a t = 0", variable=self.align_time_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        self._entry(grid_box, "Paso grilla X", self.grid_x_step_var)
        self._entry(grid_box, "Paso grilla Y", self.grid_y_step_var)
        ttk.Checkbutton(grid_box, text="Escala logarítmica X", variable=self.log_x_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(grid_box, text="Escala logarítmica Y", variable=self.log_y_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)

        shift_box = ttk.LabelFrame(left, text="Ajuste temporal / fase")
        shift_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(shift_box, text="Mover canal seleccionado en X", variable=self.shift_channel_mode, command=self._toggle_shift_channel_mode).pack(anchor="w", padx=8, pady=2)
        shift_row = ttk.Frame(shift_box)
        shift_row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(shift_row, text="Canal:").pack(side=tk.LEFT)
        self.shift_channel_menu = ttk.OptionMenu(shift_row, self.shift_channel_var, "")
        self.shift_channel_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Label(shift_box, text="También podés escribir el desplazamiento X de cada canal en la lista de canales.", wraplength=260).pack(fill=tk.X, padx=8, pady=(2, 6))

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
        self.root.bind("<Left>", lambda e: self._handle_left_right_key(-1, e))
        self.root.bind("<Right>", lambda e: self._handle_left_right_key(1, e))

    def _plot_empty(self) -> None:
        self.ax.clear()
        self.ax.text(0.5, 0.5, "Cargá un CSV para comenzar", ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_axis_off()
        self.canvas.draw_idle()

    def open_file(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar uno o más CSV",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if paths:
            self.load_files(list(paths))

    def _on_drop(self, event) -> None:
        raw = event.data.strip()
        paths = list(self.root.tk.splitlist(raw))
        if paths:
            self.load_files(paths)

    def load_file(self, path: str) -> None:
        """Compatibilidad: agrega un único archivo al gráfico actual."""
        self.load_files([path])

    def _unique_channel_name(self, base: str) -> str:
        """Evita nombres repetidos cuando se cargan varios CSV."""
        if base not in self.channels:
            return base
        i = 2
        while f"{base} ({i})" in self.channels:
            i += 1
        return f"{base} ({i})"

    def load_files(self, paths: list[str]) -> None:
        """Carga uno o varios CSV y coloca cada canal encontrado como un canal independiente.

        Si se arrastran dos CSV a la vez, los canales de ambos quedan en el mismo gráfico.
        Cada canal conserva su propio eje de tiempo, por eso no hace falta que todos los
        archivos tengan exactamente las mismas muestras.
        """
        valid_paths: list[str] = []
        rejected: list[str] = []

        for path in paths:
            path = os.path.abspath(path)
            if not path.lower().endswith(".csv"):
                rejected.append(os.path.basename(path))
                continue
            if not os.path.exists(path):
                rejected.append(os.path.basename(path))
                continue
            valid_paths.append(path)

        if not valid_paths:
            messagebox.showwarning("Archivo rechazado", "No se recibió ningún archivo .csv válido.")
            self.status_var.set("Archivo rechazado: no es .csv")
            return

        new_channels: dict[str, np.ndarray] = {}
        new_times: dict[str, np.ndarray] = {}
        new_kinds: dict[str, str] = {}
        loaded_info: list[str] = []
        last_units: list[str] = []

        # No limpiamos lo anterior: cada operación de abrir/drop AGREGA canales
        # para poder superponer CSV tirados en momentos distintos.

        for path in valid_paths:
            try:
                time, channels, units, kind = self._read_any_csv(path)
            except Exception as exc:
                rejected.append(f"{os.path.basename(path)} ({exc})")
                continue

            if time.size == 0 or len(channels) == 0:
                rejected.append(f"{os.path.basename(path)} (sin datos)")
                continue

            stem = os.path.splitext(os.path.basename(path))[0]
            for ch_name, y in channels.items():
                # Prefijamos siempre con el nombre del archivo para distinguir
                # CSV cargados en operaciones separadas.
                base_name = f"{stem} - {ch_name}"
                final_name = self._unique_channel_name(base_name)
                self.channels[final_name] = y
                self.channel_times[final_name] = time
                final_kind = self._kind_for_channel(kind, ch_name)
                self.channel_kinds[final_name] = final_kind
                new_channels[final_name] = y
                new_times[final_name] = time
                new_kinds[final_name] = final_kind

            loaded_info.append(f"{os.path.basename(path)}: {len(time)} muestras, {len(channels)} canal(es)")
            last_units = units

        if not new_channels:
            messagebox.showerror("No se pudo leer ningún CSV", "Revisá el formato de los archivos.\n\n" + "\n".join(rejected))
            self.status_var.set("Error al leer los CSV")
            return

        for path in valid_paths:
            if path not in self.file_paths:
                self.file_paths.append(path)
        self.file_path = self.file_paths[0] if self.file_paths else valid_paths[0]
        # self.time queda para compatibilidad con partes viejas del código; las curvas usan channel_times.
        self.time = next(iter(self.channel_times.values()))
        self.units_row = last_units

        if len(self.file_paths) == 1:
            self.file_label.config(text=os.path.basename(self.file_paths[0]))
        else:
            self.file_label.config(text=f"{len(self.file_paths)} CSV cargados")

        total_samples = sum(len(t) for t in self.channel_times.values())
        kinds_loaded = sorted(set(new_kinds.values()))
        tipo_txt = ", ".join(kinds_loaded)
        tipo_txt = (
            tipo_txt
            .replace("bode_mag", "Bode magnitud")
            .replace("bode_phase", "Bode fase")
            .replace("time", "tiempo")
        )
        self.status_var.set(
            f"Agregados {len(new_channels)} canal(es) de {len(valid_paths)} archivo(s) ({tipo_txt}). "
            f"Total: {len(self.channels)} canal(es), {total_samples} muestras"
        )
        if rejected:
            messagebox.showwarning(
                "Algunos archivos se omitieron",
                "Se cargaron los CSV válidos, pero se omitieron:\n\n" + "\n".join(rejected),
            )

        self._rebuild_channel_controls()
        self._rebuild_xy_menus()
        self._rebuild_cursor_channel_menu()
        self._rebuild_shift_channel_menu()
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

    def _read_any_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str], str]:
        """Detecta automáticamente si el CSV es temporal/osciloscopio o Bode.

        Tipos soportados:
        - Osciloscopio/transitorio: tiempo + canales.
        - Bode de LTspice: Freq. + celdas tipo (magnituddB,fase°).
        - Bode exportado del osciloscopio: columnas tipo Frequency, Amplitude,
          Gain (dB) y Phase.
        """
        if self._looks_like_ltspice_bode(path):
            x, channels, units = self._read_ltspice_bode_csv(path)
            return x, channels, units, "bode"

        if self._looks_like_named_bode_csv(path):
            x, channels, units = self._read_named_bode_csv(path)
            return x, channels, units, "bode"

        x, channels, units = self._read_oscilloscope_csv(path)
        return x, channels, units, "time"

    def _kind_for_channel(self, file_kind: str, channel_label: str) -> str:
        """Clasifica cada canal dentro de un archivo.

        En archivos Bode no hay que graficar todas las columnas como si fueran señales.
        La magnitud y la fase se mandan a subgráficos distintos.
        """
        if file_kind != "bode":
            return file_kind
        label = channel_label.lower()
        if "phase" in label or "fase" in label or "°" in label:
            return "bode_phase"
        return "bode_mag"

    def _looks_like_named_bode_csv(self, path: str) -> bool:
        """Detecta Bode tabular: Frequency/Amplitude/Gain/Phase."""
        sep = self._detect_delimiter(path)
        try:
            df = pd.read_csv(path, sep=sep, nrows=5, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        except Exception:
            return False
        cols = [str(c).strip().lower() for c in df.columns]
        has_freq = any("freq" in c or "frequency" in c or "frecuencia" in c for c in cols)
        has_gain = any(("gain" in c and "db" in c) or "db" in c or "magnitud" in c for c in cols)
        has_phase = any("phase" in c or "fase" in c for c in cols)
        return has_freq and (has_gain or has_phase)

    def _read_named_bode_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        """Lee Bode con columnas nombradas.

        Ejemplos de columnas:
            Frequency (Hz), Amplitude (Vpp), Gain (dB), Phase (°)

        Para el gráfico Bode se usan solamente Gain(dB) y Phase(°). La columna
        Frequency se usa como eje X y no se grafica como canal.
        """
        sep = self._detect_delimiter(path)
        df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        if df.shape[1] < 2:
            raise ValueError("el Bode tiene menos de dos columnas")

        cols = list(df.columns)
        low = [str(c).strip().lower() for c in cols]

        def find_col(pred):
            for original, l in zip(cols, low):
                if pred(l):
                    return original
            return None

        freq_col = find_col(lambda c: "freq" in c or "frequency" in c or "frecuencia" in c)
        gain_col = find_col(lambda c: ("gain" in c and "db" in c) or "db" in c or "magnitud" in c)
        phase_col = find_col(lambda c: "phase" in c or "fase" in c)

        if freq_col is None:
            raise ValueError("no se encontró columna de frecuencia")

        freq = pd.to_numeric(df[freq_col], errors="coerce").to_numpy(dtype=float)
        channels: dict[str, np.ndarray] = {}

        if gain_col is not None:
            gain = pd.to_numeric(df[gain_col], errors="coerce").to_numpy(dtype=float)
            if (np.isfinite(freq) & np.isfinite(gain)).any():
                channels["Ganancia [dB]"] = gain

        if phase_col is not None:
            phase = pd.to_numeric(df[phase_col], errors="coerce").to_numpy(dtype=float)
            if (np.isfinite(freq) & np.isfinite(phase)).any():
                channels["Fase [°]"] = phase

        if not channels:
            raise ValueError("no se encontraron columnas Gain(dB) ni Phase")

        return freq, channels, ["Hz", "dB", "°"]

    def _looks_like_ltspice_bode(self, path: str) -> bool:
        sep = self._detect_delimiter(path)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                header = f.readline().strip()
                first_data = f.readline().strip()
        except Exception:
            return False

        header_cols = re.split(rf"{re.escape(sep)}", header) if header else []
        if not header_cols:
            return False

        first_col = header_cols[0].strip().lower()
        return (
            first_col.startswith("freq")
            and "(" in first_data
            and "db" in first_data.lower()
            and "," in first_data
        )

    def _parse_bode_cell(self, value) -> tuple[float, Optional[float]]:
        """Parsea celdas LTspice tipo '(magnituddB,fase)'.

        Devuelve (magnitud_db, fase_grados). Si no encuentra fase, la fase es None.
        """
        text = str(value).strip()
        text = text.strip('"').strip("'").strip()
        text = text.strip("()")
        # Ejemplo: '2.5e-4dB,-1.47e-1'
        parts = [p.strip() for p in text.split(",")]
        mag_txt = parts[0].replace("dB", "").replace("DB", "").replace("db", "").strip()
        mag = float(mag_txt)
        phase = None
        if len(parts) > 1 and parts[1] != "":
            phase = float(parts[1].replace("°", "").strip())
        return mag, phase

    def _read_ltspice_bode_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        sep = self._detect_delimiter(path)
        df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        if df.shape[1] < 2:
            raise ValueError("el Bode tiene menos de dos columnas")

        freq = pd.to_numeric(df.iloc[:, 0], errors="coerce").to_numpy(dtype=float)
        channels: dict[str, np.ndarray] = {}

        for col in df.columns[1:]:
            mags: list[float] = []
            phases: list[float] = []
            for cell in df[col]:
                try:
                    mag, phase = self._parse_bode_cell(cell)
                except Exception:
                    mag, phase = np.nan, np.nan
                mags.append(mag)
                phases.append(np.nan if phase is None else phase)

            mag_y = np.asarray(mags, dtype=float)
            phase_y = np.asarray(phases, dtype=float)
            base = str(col).strip()

            if (np.isfinite(freq) & np.isfinite(mag_y)).any():
                channels[f"{base} - Ganancia [dB]"] = mag_y
            if (np.isfinite(freq) & np.isfinite(phase_y)).any():
                channels[f"{base} - Fase [°]"] = phase_y

        if not channels:
            raise ValueError("no se encontraron magnitud/fase en el CSV de Bode")

        return freq, channels, ["Hz", "dB", "°"]

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
            df = pd.read_csv(path, sep=sep, skiprows=2, header=None, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
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
            raise ValueError("el CSV tiene menos de dos columnas numéricas")
        time = numeric.iloc[:, 0].to_numpy(dtype=float)
        channels = {str(labels[i]) if i < len(labels) else f"Canal {i}": numeric.iloc[:, i].to_numpy(dtype=float)
                    for i in range(1, numeric.shape[1])}
        return time, channels, []

    def _rebuild_channel_controls(self) -> None:
        # Conserva los valores que el usuario ya había puesto al agregar más CSV.
        old_controls = self.controls.copy()

        for child in self.channel_inner.winfo_children():
            child.destroy()
        self.controls.clear()

        for idx, name in enumerate(self.channels.keys()):
            box = ttk.Frame(self.channel_inner, padding=4)
            box.pack(fill=tk.X, pady=2)

            old = old_controls.get(name)
            enabled = tk.BooleanVar(value=old.enabled.get() if old else True)
            scale = tk.StringVar(value=old.scale.get() if old else "1")
            offset = tk.StringVar(value=old.offset.get() if old else "0")
            x_offset = tk.StringVar(value=old.x_offset.get() if old and hasattr(old, "x_offset") else "0")
            color = tk.StringVar(value=old.color.get() if old else DEFAULT_COLORS[idx % len(DEFAULT_COLORS)])
            self.controls[name] = ChannelControls(name, enabled, scale, offset, x_offset, color)

            ttk.Checkbutton(box, text=name, variable=enabled, command=self.update_plot).grid(row=0, column=0, columnspan=4, sticky="w")
            ttk.Label(box, text="Escala Y").grid(row=1, column=0, sticky="w")
            ttk.Entry(box, textvariable=scale, width=8).grid(row=1, column=1, sticky="ew")
            ttk.Label(box, text="Offset Y").grid(row=1, column=2, sticky="w", padx=(6, 0))
            ttk.Entry(box, textvariable=offset, width=8).grid(row=1, column=3, sticky="ew")

            ttk.Label(box, text="Offset X").grid(row=2, column=0, sticky="w")
            ttk.Entry(box, textvariable=x_offset, width=8).grid(row=2, column=1, sticky="ew")
            ttk.Label(box, text=f"[{self.x_unit_var.get()}]").grid(row=2, column=2, sticky="w", padx=(6, 0))
            ttk.Button(box, text="Color", command=lambda n=name: self._choose_color(n)).grid(row=2, column=3, sticky="ew")

            for v in (scale, offset, x_offset):
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

    def _rebuild_shift_channel_menu(self) -> None:
        names = list(self.channels.keys())
        if names and self.shift_channel_var.get() not in names:
            self.shift_channel_var.set(names[0])
        elif not names:
            self.shift_channel_var.set("")

        if not hasattr(self, "shift_channel_menu"):
            return
        menu = self.shift_channel_menu["menu"]
        menu.delete(0, "end")
        for name in names:
            menu.add_command(label=name, command=lambda value=name: self.shift_channel_var.set(value))

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

    def _time_for_channel_display(self, name: str) -> Optional[np.ndarray]:
        """Devuelve el eje X del canal.

        - Canales temporales: tiempo en la unidad elegida, con alineación a t=0
          y offset X manual si corresponde.
        - Canales Bode: frecuencia en Hz, sin alineación temporal ni offset X.
        """
        t = self.channel_times.get(name, self.time)
        if t is None:
            return None

        t = np.asarray(t, dtype=float)
        kind = self.channel_kinds.get(name, "time")

        if kind in {"bode_mag", "bode_phase"}:
            # En Bode el eje X es frecuencia en Hz. No se escala a us/ms ni se alinea a t=0.
            return t

        if self.align_time_var.get() and t.size > 0:
            finite = np.isfinite(t)
            if finite.any():
                t = t - t[finite][0]

        x_factor = X_UNITS.get(self.x_unit_var.get(), 1.0)
        x = t * x_factor

        ctrl = self.controls.get(name)
        if ctrl is not None:
            x = x + self._safe_float(ctrl.x_offset.get(), 0.0)

        return x

    def _y_for_channel_display(self, name: str) -> np.ndarray:
        """Devuelve el eje Y ya transformado.

        Para Bode, la magnitud ya viene en dB; no se multiplica por V/mV.
        """
        y = self._transformed_channel(name)
        if self.channel_kinds.get(name, "time") in {"bode_mag", "bode_phase"}:
            return y
        y_factor = Y_UNITS.get(self.y_unit_var.get(), 1.0)
        return y * y_factor

    def update_plot(self) -> None:
        if self.time is None or not self.channels:
            return

        self.fig.clear()
        self.cursor_artists.clear()

        y_factor = Y_UNITS.get(self.y_unit_var.get(), 1.0)
        enabled_names = [
            name for name in self.channels.keys()
            if name in self.controls and self.controls[name].enabled.get()
        ]
        enabled_kinds = {self.channel_kinds.get(name, "time") for name in enabled_names}
        only_bode = bool(enabled_names) and enabled_kinds.issubset({"bode_mag", "bode_phase"})

        if only_bode:
            self._plot_bode(enabled_names)
            self.fig.tight_layout()
            self.canvas.draw_idle()
            return

        self.ax = self.fig.add_subplot(111)
        self.ax.set_axis_on()

        if self.xy_mode_var.get():
            self._plot_xy(y_factor)
        else:
            for name in enabled_names:
                ctrl = self.controls[name]
                x = self._time_for_channel_display(name)
                if x is None:
                    continue
                y = self._y_for_channel_display(name)
                self.ax.plot(x, y, label=name, color=ctrl.color.get())
                self._mark_points(x, y, name, ctrl.color.get())

            if {"bode_mag", "bode_phase"} & enabled_kinds:
                self.ax.set_xlabel("X: tiempo o frecuencia")
                self.ax.set_ylabel("Y: tensión, magnitud o fase")
                self.ax.text(
                    0.02, 0.02,
                    "Aviso: hay canales temporales y Bode activos a la vez.\n"
                    "Para ver el Bode correcto, dejá activos solo canales Bode.",
                    transform=self.ax.transAxes,
                    fontsize=8,
                    va="bottom",
                )
            else:
                self.ax.set_xlabel(f"{self.xlabel_var.get()} [{self.x_unit_var.get()}]")
                self.ax.set_ylabel(f"{self.ylabel_var.get()} [{self.y_unit_var.get()}]")

        self.ax.set_title(self.title_var.get())
        self._apply_grid_and_scales()

        if enabled_names:
            self.ax.legend(loc="best")
        self._redraw_cursors()
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _plot_bode(self, enabled_names: list[str]) -> None:
        """Grafica Bode verdadero: magnitud(dB) y fase(°) vs frecuencia logarítmica."""
        ax_mag = self.fig.add_subplot(211)
        ax_phase = self.fig.add_subplot(212, sharex=ax_mag)
        self.ax = ax_mag

        mag_count = 0
        phase_count = 0

        for name in enabled_names:
            kind = self.channel_kinds.get(name, "time")
            x = self._time_for_channel_display(name)
            if x is None:
                continue
            y = self._y_for_channel_display(name)
            ctrl = self.controls[name]
            finite = np.isfinite(x) & np.isfinite(y) & (x > 0)
            if not finite.any():
                continue
            xf = np.asarray(x, dtype=float)[finite]
            yf = np.asarray(y, dtype=float)[finite]

            if kind == "bode_phase":
                ax_phase.semilogx(xf, yf, label=name, color=ctrl.color.get())
                phase_count += 1
            else:
                ax_mag.semilogx(xf, yf, label=name, color=ctrl.color.get())
                mag_count += 1

        ax_mag.set_title(self.title_var.get() if self.title_var.get() else "Diagrama de Bode")
        ax_mag.set_ylabel("Magnitud [dB]")
        ax_phase.set_ylabel("Fase [°]")
        ax_phase.set_xlabel("Frecuencia [Hz]")

        if self.grid_var.get():
            ax_mag.grid(True, which="both", alpha=0.35)
            ax_phase.grid(True, which="both", alpha=0.35)
        else:
            ax_mag.grid(False)
            ax_phase.grid(False)

        if mag_count:
            ax_mag.legend(loc="best")
        else:
            ax_mag.text(0.5, 0.5, "No hay canal de magnitud/Gain [dB] activo", ha="center", va="center", transform=ax_mag.transAxes)

        if phase_count:
            ax_phase.legend(loc="best")
        else:
            ax_phase.text(0.5, 0.5, "No hay canal de fase activo", ha="center", va="center", transform=ax_phase.transAxes)

    def _plot_xy(self, y_factor: float) -> None:
        x_name = self.xy_x_var.get()
        y_name = self.xy_y_var.get()
        if x_name not in self.channels or y_name not in self.channels:
            self.ax.text(0.5, 0.5, "Elegí dos canales válidos", ha="center", va="center", transform=self.ax.transAxes)
            return

        tx = self.channel_times.get(x_name, self.time)
        ty = self.channel_times.get(y_name, self.time)
        if tx is None or ty is None:
            return

        x_data = self._transformed_channel(x_name) * y_factor
        y_data = self._transformed_channel(y_name) * y_factor

        # Si vienen de CSV distintos, pueden tener ejes de tiempo distintos.
        # Para modo XY interpolamos Y sobre el eje temporal de X.
        if len(x_data) != len(y_data) or not np.array_equal(tx, ty):
            finite_x = np.isfinite(tx) & np.isfinite(x_data)
            finite_y = np.isfinite(ty) & np.isfinite(y_data)
            txf, xdf = tx[finite_x], x_data[finite_x]
            tyf, ydf = ty[finite_y], y_data[finite_y]
            if txf.size == 0 or tyf.size == 0:
                return
            order_y = np.argsort(tyf)
            y_interp = np.interp(txf, tyf[order_y], ydf[order_y])
            x_plot = xdf
            y_plot = y_interp
        else:
            x_plot = x_data
            y_plot = y_data

        color = self.controls.get(y_name, next(iter(self.controls.values()))).color.get()
        self.ax.plot(x_plot, y_plot, color=color, label=f"{y_name} vs {x_name}")
        self.ax.set_xlabel(f"{x_name} [{self.y_unit_var.get()}]")
        self.ax.set_ylabel(f"{y_name} [{self.y_unit_var.get()}]")
        self._mark_points(x_plot, y_plot, y_name, color)

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

    def _toggle_shift_channel_mode(self) -> None:
        if self.shift_channel_mode.get():
            self.cursor_mode.set(False)
            self.move_cursor_mode.set(False)
            self.dragging_cursor = False
            self.status_var.set("Ajuste temporal: elegí un canal y arrastrá horizontalmente el mouse, o usá flechas izquierda/derecha.")
        else:
            self.dragging_channel_shift = False
            self.last_shift_x = None
            self.status_var.set("Modo ajuste temporal desactivado")

    def _selected_shift_channel(self) -> Optional[str]:
        name = self.shift_channel_var.get()
        return name if name in self.channels and name in self.controls else None

    def _channel_step_display_units(self, channel: str) -> float:
        x = self._time_for_channel_display(channel)
        if x is None:
            return 1.0
        x = np.asarray(x, dtype=float)
        finite = np.isfinite(x)
        if finite.sum() < 2:
            return 1.0
        xs = np.sort(np.unique(x[finite]))
        diffs = np.diff(xs)
        diffs = diffs[diffs > 0]
        if diffs.size == 0:
            return 1.0
        return float(np.median(diffs))

    def _shift_channel_by(self, channel: str, dx_display_units: float) -> None:
        ctrl = self.controls.get(channel)
        if ctrl is None:
            return
        current = self._safe_float(ctrl.x_offset.get(), 0.0)
        new_value = current + dx_display_units
        ctrl.x_offset.set(f"{new_value:.8g}")
        self.status_var.set(f"{channel}: offset X = {new_value:.8g} {self.x_unit_var.get()}")
        # El trace del StringVar ya llama a update_plot(), pero forzamos que los cursores se refresquen bien.
        self._refresh_cursor_tree()

    def _handle_left_right_key(self, direction: int, event=None):
        if self.shift_channel_mode.get():
            channel = self._selected_shift_channel()
            if channel is None:
                return "break"
            step = self._channel_step_display_units(channel)
            # Shift + flecha mueve 10 muestras; Ctrl + flecha mueve 0.1 muestra.
            state = getattr(event, "state", 0) if event is not None else 0
            if state & 0x0001:
                step *= 10
            if state & 0x0004:
                step *= 0.1
            self._shift_channel_by(channel, direction * step)
            return "break"
        self._move_selected_cursor_by_key(direction)
        return "break"

    def _toggle_cursor_mode(self) -> None:
        if self.cursor_mode.get():
            self.move_cursor_mode.set(False)
            self.shift_channel_mode.set(False)
            self.status_var.set("Cursores: elegí un canal y hacé clic. Cada clic agrega un cursor; Y se calcula automáticamente.")
        else:
            self.status_var.set("Modo agregar cursor desactivado")

    def _toggle_move_cursor_mode(self) -> None:
        if self.move_cursor_mode.get():
            self.cursor_mode.set(False)
            self.shift_channel_mode.set(False)
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

        if self.shift_channel_mode.get():
            channel = self._selected_shift_channel()
            if channel is None:
                messagebox.showwarning("Sin canal", "Seleccioná un canal para desplazarlo en X.")
                return
            self.dragging_channel_shift = True
            self.last_shift_x = float(event.xdata)
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
        if self.dragging_channel_shift and self.shift_channel_mode.get():
            if event.inaxes != self.ax or event.xdata is None or self.last_shift_x is None:
                return
            channel = self._selected_shift_channel()
            if channel is not None:
                x_now = float(event.xdata)
                dx = x_now - self.last_shift_x
                self.last_shift_x = x_now
                self._shift_channel_by(channel, dx)
            return

        if not self.dragging_cursor or not self.move_cursor_mode.get():
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        cursor = self._selected_cursor()
        if cursor is not None:
            self._move_cursor_to_x(cursor, float(event.xdata))

    def _on_plot_release(self, _event) -> None:
        self.dragging_cursor = False
        self.dragging_channel_shift = False
        self.last_shift_x = None

    def _interp_channel_y(self, channel: str, x_display_units: float) -> float:
        """Devuelve Y del canal en las unidades mostradas, interpolando según X mostrada."""
        xdata = self._time_for_channel_display(channel)
        if xdata is None:
            return 0.0
        ydata = self._y_for_channel_display(channel)
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
        xdata = self._time_for_channel_display(cursor.channel)
        if xdata is None:
            return
        xdata = np.asarray(xdata, dtype=float)
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

    def clear_all_files(self) -> None:
        """Limpia todos los CSV, canales, controles y cursores."""
        self.file_path = None
        self.file_paths = []
        self.raw_df = None
        self.units_row = []
        self.time = None
        self.channel_times.clear()
        self.channel_kinds.clear()
        self.channels.clear()
        self.controls.clear()
        self.cursors.clear()
        self.selected_cursor_id = None
        self.cursor_x_var.set("")
        self.cursor_y_var.set("")
        self.file_label.config(text="Ningún archivo cargado")
        for child in self.channel_inner.winfo_children():
            child.destroy()
        self._rebuild_xy_menus()
        self._rebuild_cursor_channel_menu()
        self._refresh_cursor_tree()
        self.status_var.set("Cargá un archivo .csv")
        self._plot_empty()

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
