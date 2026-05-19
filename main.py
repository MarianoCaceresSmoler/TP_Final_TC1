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
        self.cursor_clicks: list[float] = []
        self.cursor_lines = []
        self.cursor_text = None
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

        markers_box = ttk.LabelFrame(left, text="Puntos importantes y cursores")
        markers_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Checkbutton(markers_box, text="Marcar máximos", variable=self.mark_max_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(markers_box, text="Marcar mínimos", variable=self.mark_min_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Checkbutton(markers_box, text="Cursores caseros", variable=self.cursor_mode, command=self._toggle_cursor_mode).pack(anchor="w", padx=8, pady=2)
        ttk.Button(markers_box, text="Borrar cursores", command=self._clear_cursors).pack(fill=tk.X, padx=8, pady=4)

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
        self._clear_cursors(draw=False)

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
        if not self.cursor_mode.get():
            self._clear_cursors()
        else:
            self.status_var.set("Cursores: hacé dos clics sobre el gráfico para medir Δx y Δy")

    def _on_plot_click(self, event) -> None:
        if not self.cursor_mode.get() or event.inaxes != self.ax or event.xdata is None:
            return
        self.cursor_clicks.append(float(event.xdata))
        if len(self.cursor_clicks) > 2:
            self.cursor_clicks = [self.cursor_clicks[-1]]
            self._clear_cursors(draw=False)

        line = self.ax.axvline(event.xdata, linestyle="--", linewidth=1)
        self.cursor_lines.append(line)

        if len(self.cursor_clicks) == 2:
            x1, x2 = self.cursor_clicks
            dx = x2 - x1
            msg = f"x1={x1:.6g}, x2={x2:.6g}, Δx={dx:.6g} {self.x_unit_var.get() if not self.xy_mode_var.get() else self.y_unit_var.get()}"
            self.status_var.set(msg)
            self.cursor_text = self.ax.text(0.02, 0.98, msg, transform=self.ax.transAxes, va="top", bbox={"boxstyle": "round", "alpha": 0.2})
        self.canvas.draw_idle()

    def _clear_cursors(self, draw: bool = True) -> None:
        self.cursor_clicks.clear()
        for line in self.cursor_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.cursor_lines.clear()
        if self.cursor_text is not None:
            try:
                self.cursor_text.remove()
            except Exception:
                pass
            self.cursor_text = None
        if draw:
            self.canvas.draw_idle()


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
