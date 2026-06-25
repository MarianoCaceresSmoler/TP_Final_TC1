"""
@file channel_panel.py
@brief channel table, channel editor, mode widgets, and menu synchronization methods.
"""

from __future__ import annotations

from .common import *


class ChannelPanelMixin:
    """
    @brief Mixin that groups channel table, channel editor, mode widgets, and menu synchronization methods.
    """
    def _sync_after_data_change(self) -> None:
        """
        @brief Refresh all UI elements and the plot after channels or files change.
        """
        self._update_mode_labels()
        self._refresh_channel_tree()
        self._rebuild_channel_menus()
        self._refresh_cursor_tree()
        self.update_plot()

    def _update_mode_labels(self) -> None:
        """
        @brief Update mode labels, loaded-file text, unit labels, and mode-specific widgets.
        """
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
        """
        @brief Show or hide controls depending on whether the current mode is empty, time, or Bode.
        """
        # Hide time-domain tools when the application is working in Bode mode.
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
            # Empty screen: show general tools and time-domain controls by default.
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
        """
        @brief Rebuild the channel table from the current channel and control dictionaries.
        """
        for item in self.channel_tree.get_children():
            self.channel_tree.delete(item)
        for name, data in self.channels.items():
            ctrl = self.controls[name]
            tipo = {"time": "Tiempo", "bode_mag": "Bode dB", "bode_phase": "Bode °"}[data.kind]
            on = "✓" if ctrl.enabled.get() else "—"
            ox = ctrl.offset_x.get() if data.kind == "time" else ""
            self.channel_tree.insert("", "end", iid=name, text=name, values=(on, tipo, ctrl.scale_y.get(), ctrl.offset_y.get(), ox))

    def _rebuild_channel_menus(self) -> None:
        """
        @brief Rebuild all OptionMenu widgets that depend on the current list of channels.
        """
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
        """
        @brief Replace all items inside an OptionMenu and keep its variable valid.
        
        @param widget: OptionMenu to rebuild.
        @param var: StringVar controlled by the menu.
        @param values: New list of valid menu values.
        @param callback: Optional callback executed after a menu value is selected.
        """
        menu = widget["menu"]
        menu.delete(0, "end")
        if values and var.get() not in values:
            var.set(values[0])
        elif not values:
            var.set("")
        for value in values:
            menu.add_command(label=value, command=lambda v=value: (var.set(v), callback() if callback else None))

    def _on_channel_select(self, _event=None) -> None:
        """
        @brief Load the selected channel settings into the channel editor controls.
        """
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
        """
        @brief Apply the channel editor values to the selected channel.
        """
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
        """
        @brief Reset the selected channel scale and offsets to default values.
        """
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
        """
        @brief Toggle visibility for the selected channel in the channel table.
        """
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
        """
        @brief Open the color picker and apply the chosen color to the selected channel.
        """
        selected = self.channel_tree.selection()
        if not selected:
            messagebox.showinfo("Color", "Seleccioná un canal de la tabla.")
            return
        name = selected[0]
        ctrl = self.controls[name]
        # Tkinter colorchooser does not accept Matplotlib color names such as "tab:blue".
        # Use a safe initial color if an old Matplotlib color name was stored.
        initial_color = ctrl.color.get()
        if not str(initial_color).startswith("#"):
            initial_color = "#1f77b4"
        chosen = colorchooser.askcolor(color=initial_color, title=f"Color para {name}")
        if chosen and chosen[1]:
            ctrl.color.set(chosen[1])
            # Also update cursors that belong to this channel.
            for cursor in self.cursors:
                if cursor.channel == name:
                    cursor.color = chosen[1]
            self._refresh_channel_tree()
            self._refresh_cursor_tree()
            self.update_plot()
            self.status_var.set(f"Color actualizado para {name}")

    def _on_shift_channel_changed(self) -> None:
        """
        @brief Update the X-offset entry when the selected shift channel changes.
        """
        name = self.shift_channel_var.get()
        if name in self.controls:
            self.shift_x_var.set(self.controls[name].offset_x.get())

    # ------------------------------------------------------------------
    # Data transformations and plotting
    # ------------------------------------------------------------------
