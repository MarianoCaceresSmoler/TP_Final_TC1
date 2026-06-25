"""
@file plotting.py
@brief data transformation and Matplotlib plotting methods.
"""

from __future__ import annotations

from .common import *


class PlottingMixin:
    """
    @brief Mixin that groups data transformation and matplotlib plotting methods.
    """
    def _safe_float(self, text: str, default: float = 0.0) -> float:
        """
        @brief Convert user-entered text to a float using a default when conversion fails.
        
        @param text: User-entered text to convert.
        @param default: Value returned when conversion fails or the text is empty.
        @return: Converted floating-point value or the provided default.
        """
        try:
            text = str(text).replace(",", ".").strip()
            return float(text) if text else default
        except Exception:
            return default

    def _x_display(self, name: str) -> np.ndarray:
        """
        @brief Return the X array of a channel after unit conversion, alignment, and X offset.
        
        @param name: Channel name.
        @return: Displayed X array for the requested channel.
        """
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
        """
        @brief Return the Y array of a channel after scale, offset, and unit conversion.
        
        @param name: Channel name.
        @return: Displayed Y array for the requested channel.
        """
        data = self.channels[name]
        ctrl = self.controls[name]
        y = np.asarray(data.y, dtype=float)
        y = y * self._safe_float(ctrl.scale_y.get(), 1.0) + self._safe_float(ctrl.offset_y.get(), 0.0)
        if data.kind == "time":
            y = y * Y_UNITS.get(self.y_unit_var.get(), 1.0)
        return y

    def update_plot(self) -> None:
        """
        @brief Clear and redraw the current plot according to the selected mode.
        """
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
        """
        @brief Draw the empty initial screen that asks the user to load CSV files.
        
        @param draw: If True, immediately requests a canvas redraw.
        """
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.ax.text(0.5, 0.5, "Cargá o arrastrá uno o más CSV", ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_axis_off()
        if draw:
            self.canvas.draw_idle()

    def _plot_time(self) -> None:
        """
        @brief Draw time-domain signals and optional maximum/minimum markers.
        """
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
        """
        @brief Draw Bode magnitude and phase on two logarithmic-frequency axes.
        """
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
        """
        @brief Draw one time-domain channel versus another as an XY/Lissajous plot.
        """
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
        """
        @brief Apply grid, logarithmic scales, and optional major grid spacing to an axis.
        
        @param ax: Matplotlib axis to configure.
        """
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
        """
        @brief Mark maximum and/or minimum points on a plotted time-domain channel.
        
        @param ax: Matplotlib axis where markers are drawn.
        @param x: Displayed X data.
        @param y: Displayed Y data.
        @param name: Channel name.
        @param color: Color used for markers and annotations.
        """
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
    # Cursor management
    # ------------------------------------------------------------------
