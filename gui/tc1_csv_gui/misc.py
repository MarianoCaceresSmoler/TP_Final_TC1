"""
@file misc.py
@brief small utility callbacks and reset methods.
"""

from __future__ import annotations

from .common import *


class MiscMixin:
    """
    @brief Mixin that groups small utility callbacks and reset methods.
    """
    def _toggle_xy(self) -> None:
        """
        @brief Enable or disable XY mode, validating that the current mode supports it.
        """
        if self.mode == "bode" and self.xy_mode_var.get():
            messagebox.showinfo("Modo XY", "El modo XY solo aplica a señales temporales.")
            self.xy_mode_var.set(False)
            return
        self.update_plot()

    def _unit_changed(self) -> None:
        """
        @brief Refresh labels, table values, and plot after the displayed X unit changes.
        """
        self._update_mode_labels()
        self._refresh_channel_tree()
        self.update_plot()

    def clear_all(self, ask: bool = True) -> None:
        """
        @brief Remove all loaded channels, files, cursors, and restore the empty state.
        
        @param ask: If True, asks for confirmation before clearing existing data.
        """
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
