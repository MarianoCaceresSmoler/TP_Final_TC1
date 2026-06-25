"""
@file ui.py
@brief Tkinter layout construction methods for the TC1 CSV GUI.
"""

from __future__ import annotations

from .common import *


class UIMixin:
    """
    @brief Mixin that groups tkinter layout construction methods for the tc1 csv gui.
    """
    def _build_layout(self) -> None:
        """
        @brief Build the main window layout, side tabs, plot area, and toolbar.
        """
        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.Frame(main, width=500)
        right = ttk.Frame(main)
        main.add(left, weight=0)
        main.add(right, weight=1)

        # Side notebook: prevents the control panel from becoming one long column.
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

        # Plot area.
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
        """
        @brief Build the file-loading, clearing, drag-and-drop, and PDF export controls.
        """
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
        """
        @brief Build graph configuration controls for time-domain plots and Bode plots.
        """
        # Common title controls.
        common = ttk.LabelFrame(self.tab_plot, text="Título")
        common.pack(fill=tk.X, pady=(0, 8))
        self._entry(common, "Título", self.title_var)

        # Time-domain specific options.
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

        # Time shift controls, available only in time-domain mode.
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

        # Bode-specific options.
        self.bode_options = ttk.LabelFrame(self.tab_plot, text="Modo Bode")
        self.bode_options.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            self.bode_options,
            text="En Bode se grafica automáticamente magnitud [dB] y fase [°] contra frecuencia [Hz] con eje X logarítmico.",
            wraplength=450,
        ).pack(fill=tk.X, padx=8, pady=(8, 6))
        ttk.Checkbutton(self.bode_options, text="Mostrar grilla", variable=self.grid_var, command=self.update_plot).pack(anchor="w", padx=8, pady=2)
        ttk.Label(self.bode_options, text="Los cursores de Bode están en la pestaña Cursores.", wraplength=450).pack(fill=tk.X, padx=8, pady=(4, 8))

        # Common visualization options.
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
        """
        @brief Build the channel table and controls for visibility, offsets, scale, and color.
        """
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
        """
        @brief Build the cursor creation, editing, moving, deleting, and comparison controls.
        """
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
        """
        @brief Create a labeled text entry bound to a Tkinter StringVar.
        
        @param parent: Frame that will contain the label and entry.
        @param label: Text shown next to the entry.
        @param var: StringVar bound to the entry value.
        @return: Created ttk.Entry widget.
        """
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, padx=8, pady=3)
        ttk.Label(row, text=label, width=13).pack(side=tk.LEFT)
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ent.bind("<Return>", lambda _e: self.update_plot())
        return ent

    def _connect_events(self) -> None:
        """
        @brief Connect Matplotlib mouse events and keyboard shortcuts.
        """
        self.fig.canvas.mpl_connect("button_press_event", self._on_plot_click)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_plot_motion)
        self.fig.canvas.mpl_connect("button_release_event", self._on_plot_release)
        self.root.bind("<Left>", lambda e: self._handle_left_right(-1, e))
        self.root.bind("<Right>", lambda e: self._handle_left_right(1, e))

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------
