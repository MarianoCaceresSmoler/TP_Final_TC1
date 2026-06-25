"""
@file cursors.py
@brief interactive cursor creation, movement, interpolation, and drawing methods.
"""

from __future__ import annotations

from .common import *


class CursorMixin:
    """
    @brief Mixin that groups interactive cursor creation, movement, interpolation, and drawing methods.
    """
    def _toggle_cursor_add(self) -> None:
        """
        @brief Enable cursor-add mode and disable incompatible modes.
        """
        if self.cursor_add_mode.get():
            self.cursor_move_mode.set(False)
            self.shift_mode_var.set(False)
            if self.mode == "bode":
                self.status_var.set("Cursores Bode: elegí magnitud o fase y hacé clic. La Y se calcula sola.")
            else:
                self.status_var.set("Cursores: elegí un canal y hacé clic para agregar. La Y se calcula sola.")

    def _toggle_cursor_move(self) -> None:
        """
        @brief Enable cursor-move mode and disable incompatible modes.
        """
        if self.cursor_move_mode.get():
            self.cursor_add_mode.set(False)
            self.shift_mode_var.set(False)
            self.status_var.set("Mover cursor: seleccioná uno y movelo con mouse o flechas.")

    def _on_plot_click(self, event) -> None:
        """
        @brief Handle plot clicks for cursor creation, cursor movement, or channel shifting.
        
        @param event: Matplotlib mouse click event.
        """
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
        """
        @brief Return whether a Matplotlib event belongs to the correct axis for a cursor channel.
        
        @param event: Matplotlib event to test.
        @param channel: Channel associated with the cursor.
        @return: True if the event belongs to the expected axis, otherwise False.
        """
        if channel not in self.channels:
            return False
        if self.mode == "time":
            return event.inaxes == getattr(self, "ax", None)
        if self.mode == "bode":
            kind = self.channels[channel].kind
            return event.inaxes == self.bode_axes.get(kind)
        return False

    def _on_plot_motion(self, event) -> None:
        """
        @brief Handle mouse movement while dragging a cursor or shifting a channel.
        
        @param event: Matplotlib mouse motion event.
        """
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
        """
        @brief Stop active drag operations after the mouse button is released.
        
        @param _event: Matplotlib mouse release event.
        """
        self.dragging_cursor = False
        self.dragging_channel_shift = False
        self.last_shift_x = None

    def _interp_channel_y(self, channel: str, x_val: float) -> float:
        """
        @brief Interpolate the Y value of a channel at a displayed X coordinate.
        
        @param channel: Channel name.
        @param x_val: Displayed X coordinate where Y is required.
        @return: Interpolated displayed Y value.
        """
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
        """
        @brief Create and store a cursor on a channel at a displayed X coordinate.
        
        @param channel: Channel where the cursor is created.
        @param x: Displayed X coordinate of the cursor.
        """
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
        """
        @brief Create a cursor using the channel and X value entered in the UI.
        """
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
        """
        @brief Return the currently selected cursor, if it still exists.
        
        @return: Selected CursorItem or None.
        """
        if self.selected_cursor_id is None:
            return None
        for c in self.cursors:
            if c.cursor_id == self.selected_cursor_id:
                return c
        return None

    def _update_selected_cursor_from_entry(self) -> None:
        """
        @brief Update the selected cursor using the channel and X value entered in the UI.
        """
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
        """
        @brief Move a cursor to a new displayed X coordinate and recompute its Y value.
        
        @param cur: Cursor to move.
        @param x: New displayed X coordinate.
        """
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
        """
        @brief Move the selected cursor to the next or previous sample using arrow keys.
        
        @param direction: Movement direction: -1 for left, +1 for right.
        """
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
        """
        @brief Delete the currently selected cursor.
        """
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
        """
        @brief Synchronize cursor editor fields when the cursor table selection changes.
        """
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
        """
        @brief Rebuild the cursor table and delta columns.
        """
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
        """
        @brief Rebuild the menu used to select the reference cursor for delta measurements.
        """
        values = ["Ninguno"] + [f"C{c.cursor_id} - {c.channel}" for c in self.cursors]
        if self.cursor_ref_var.get() not in values:
            self.cursor_ref_var.set("Ninguno")
        menu = self.cursor_ref_menu["menu"]
        menu.delete(0, "end")
        for v in values:
            menu.add_command(label=v, command=lambda val=v: (self.cursor_ref_var.set(val), self._refresh_cursor_tree()))

    def _cursor_by_ref(self) -> Optional[CursorItem]:
        """
        @brief Return the cursor selected as reference for delta calculations.
        
        @return: Reference CursorItem or None.
        """
        m = re.match(r"C(\d+)", self.cursor_ref_var.get())
        if not m:
            return None
        cid = int(m.group(1))
        for c in self.cursors:
            if c.cursor_id == cid:
                return c
        return None

    def _redraw_cursors(self) -> None:
        """
        @brief Draw all compatible cursors on the current plot axes.
        """
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
        """
        @brief Draw one cursor as vertical and horizontal guide lines with a point marker.
        
        @param ax: Matplotlib axis where the cursor is drawn.
        @param cursor: Cursor item to draw.
        """
        selected = cursor.cursor_id == self.selected_cursor_id
        lw = 2.0 if selected else 1.2
        size = 65 if selected else 35
        ax.axvline(cursor.x, linestyle="--", linewidth=lw, color=cursor.color, alpha=0.85)
        ax.axhline(cursor.y, linestyle=":", linewidth=lw, color=cursor.color, alpha=0.85)
        ax.scatter([cursor.x], [cursor.y], color=cursor.color, s=size, zorder=5)
        ax.annotate(f"C{cursor.cursor_id}\n{cursor.channel}", (cursor.x, cursor.y), textcoords="offset points", xytext=(7, 7), fontsize=8, color=cursor.color)

    # ------------------------------------------------------------------
    # Time shift / phase alignment
    # ------------------------------------------------------------------
