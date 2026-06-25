"""
@file time_shift.py
@brief time-domain X-offset and keyboard shifting methods.
"""

from __future__ import annotations

from .common import *


class TimeShiftMixin:
    """
    @brief Mixin that groups time-domain x-offset and keyboard shifting methods.
    """
    def _toggle_shift_mode(self) -> None:
        """
        @brief Enable or disable X-shift mode for time-domain channel alignment.
        """
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
        """
        @brief Apply the X-offset value typed by the user to the selected time-domain channel.
        """
        name = self.shift_channel_var.get()
        if name not in self.controls or self.channels[name].kind != "time":
            messagebox.showinfo("Ajuste X", "Seleccioná un canal temporal.")
            return
        self.controls[name].offset_x.set(self.shift_x_var.get())
        self._refresh_channel_tree()
        self.update_plot()

    def _shift_channel_by(self, name: str, dx: float) -> None:
        """
        @brief Increment the X offset of a time-domain channel by a displayed amount.
        
        @param name: Channel to shift.
        @param dx: Displayed X offset increment.
        """
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
        """
        @brief Estimate the displayed sample spacing of a channel.
        
        @param name: Channel name.
        @return: Estimated displayed sample spacing.
        """
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
        """
        @brief Handle left and right arrow keys for channel shifting or cursor movement.
        
        @param direction: Arrow direction: -1 for left, +1 for right.
        @param event: Optional Tkinter key event used to detect modifiers.
        @return: The string "break" to stop Tkinter from further processing the key event.
        """
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
    # Exporting
    # ------------------------------------------------------------------
