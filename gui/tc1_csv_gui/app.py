"""
@file app.py
@brief Main application class for the TC1 CSV GUI.

@details
The class is intentionally composed from mixins so that each file owns one coherent part of the
program: interface construction, CSV loading, channel controls, plotting, cursors, time shifting,
exporting, and small callbacks.
"""

from __future__ import annotations

from .common import *
from .ui import UIMixin
from .file_loading import FileLoadingMixin
from .channel_panel import ChannelPanelMixin
from .plotting import PlottingMixin
from .cursors import CursorMixin
from .time_shift import TimeShiftMixin
from .exporting import ExportingMixin
from .misc import MiscMixin


class TC1CSVGUI(
    UIMixin,
    FileLoadingMixin,
    ChannelPanelMixin,
    PlottingMixin,
    CursorMixin,
    TimeShiftMixin,
    ExportingMixin,
    MiscMixin,
):
    """
    @brief Main Tkinter application that loads, plots, edits, and exports CSV data.

    @param root: Tkinter root window used as the application parent.
    """
    def __init__(self, root: tk.Tk):
        """
        @brief Initialize the application state, build the interface, and connect events.
        
        @param root: Tkinter root window used as the application parent.
        """
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
    # User interface construction
    # ------------------------------------------------------------------

    def _build_vars(self) -> None:
        """
        @brief Create all Tkinter variables used by the interface.
        """
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


def main() -> None:
    """
    @brief Start the desktop application.
    """
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
