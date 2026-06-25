"""
@file file_loading.py
@brief CSV loading, format detection, and parsing methods.
"""

from __future__ import annotations

from .common import *


class FileLoadingMixin:
    """
    @brief Mixin that groups csv loading, format detection, and parsing methods.
    """
    def open_files(self) -> None:
        """
        @brief Open a file dialog and load the selected CSV files.
        """
        paths = filedialog.askopenfilenames(
            title="Seleccionar uno o más CSV",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if paths:
            self.load_files(list(paths))

    def _on_drop(self, event) -> None:
        """
        @brief Handle files dropped into the Tkinter window.
        
        @param event: Tkinter drag-and-drop event containing dropped file paths.
        """
        paths = list(self.root.tk.splitlist(event.data.strip()))
        if paths:
            self.load_files(paths)

    def load_files(self, paths: list[str]) -> None:
        """
        @brief Validate, parse, and load one or more CSV files into the current plotting mode.
        
        @param paths: List of file paths requested by the user.
        """
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
        """
        @brief Return a channel name that does not collide with existing channel names.
        
        @param base: Desired base channel name.
        @return: Unique channel name based on the requested base name.
        """
        if base not in self.channels:
            return base
        i = 2
        while f"{base} ({i})" in self.channels:
            i += 1
        return f"{base} ({i})"

    def _detect_delimiter(self, path: str) -> str:
        """
        @brief Detect the CSV delimiter used by a file.
        
        @param path: Path to the CSV file.
        @return: Detected delimiter character.
        """
        with open(path, "r", newline="", encoding="utf-8-sig", errors="ignore") as f:
            sample = f.read(4096)
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
        except Exception:
            return ","

    def _read_any_csv(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str], AppMode]:
        """
        @brief Detect the data format and dispatch the file to the correct CSV reader.
        
        @param path: Path to the file to read.
        @return: Tuple containing X values, channel arrays, unit labels, and detected application mode.
        """
        if self._looks_like_ltspice_bode(path):
            x, ch, units = self._read_ltspice_bode(path)
            return x, ch, units, "bode"
        if self._looks_like_named_bode(path):
            x, ch, units = self._read_named_bode(path)
            return x, ch, units, "bode"
        x, ch, units = self._read_time_csv(path)
        return x, ch, units, "time"

    def _looks_like_named_bode(self, path: str) -> bool:
        """
        @brief Check whether a CSV contains named Bode columns such as frequency, gain, or phase.
        
        @param path: Path to the candidate CSV file.
        @return: True if the file appears to contain named Bode columns, otherwise False.
        """
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
        """
        @brief Read a Bode CSV with explicit frequency, gain, and phase column names.
        
        @param path: Path to the named-column Bode CSV file.
        @return: Tuple containing frequency values, Bode channel arrays, and unit labels.
        """
        sep = self._detect_delimiter(path)
        df = pd.read_csv(path, sep=sep, engine="python", encoding="utf-8-sig", encoding_errors="ignore")
        cols = list(df.columns)
        low = [str(c).lower().strip() for c in cols]

        def find(pred):
            """
            @brief Function helper used by the GUI.
            """
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
        """
        @brief Check whether a file has the LTspice Bode export format.
        
        @param path: Path to the candidate LTspice export file.
        @return: True if the file appears to use the LTspice Bode format, otherwise False.
        """
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
        """
        @brief Parse one LTspice Bode cell into magnitude in dB and phase in degrees.
        
        @param value: Cell text in the form "(magnitude_dB, phase_deg)".
        @return: Magnitude in dB and phase in degrees.
        """
        text = str(value).strip().strip('"').strip("'").strip().strip("()")
        parts = [p.strip() for p in text.split(",")]
        mag = float(parts[0].lower().replace("db", "").strip())
        phase = float(parts[1].replace("°", "").strip()) if len(parts) > 1 and parts[1] else np.nan
        return mag, phase

    def _read_ltspice_bode(self, path: str) -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
        """
        @brief Read an LTspice Bode export and split each trace into magnitude and phase channels.
        
        @param path: Path to the LTspice Bode export file.
        @return: Tuple containing frequency values, magnitude/phase channel arrays, and unit labels.
        """
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
        """
        @brief Read a time-domain CSV file from an oscilloscope or generic table.
        
        @param path: Path to the time-domain CSV file.
        @return: Tuple containing time values, channel arrays, and unit labels.
        """
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
    # UI synchronization
    # ------------------------------------------------------------------
