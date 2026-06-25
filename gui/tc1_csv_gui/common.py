"""
@file common.py
@brief Shared imports, constants, optional dependencies, and data containers for the TC1 CSV GUI.

@details
This module contains only definitions that are used by several parts of the application. Keeping
these objects in one place avoids repeated constants and makes the rest of the project easier to
read.
"""

from __future__ import annotations

import csv
import os
import re
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Literal, Optional

import matplotlib
# TkAgg is the intended backend for the desktop application.
# In headless environments this backend may be unavailable, so the import is kept safe.
try:
    matplotlib.use("TkAgg")
except ImportError:
    pass

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


AppMode = Literal["empty", "time", "bode"]
ChannelKind = Literal["time", "bode_mag", "bode_phase"]

X_UNITS = {"s": 1.0, "ms": 1e3, "us": 1e6, "µs": 1e6, "ns": 1e9}
Y_UNITS = {"V": 1.0, "mV": 1e3}

# Colors are stored in HEX format.
# Tkinter colorchooser does not understand Matplotlib color names such as "tab:blue".
# HEX values are used because they work in both Tkinter and Matplotlib.
DEFAULT_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


@dataclass
class ChannelData:
    """
    @brief Container for one plotted data channel.

    @ivar name: Human-readable channel name shown in tables and legends.
    @ivar x: Raw X values. For time plots this is time; for Bode plots this is frequency.
    @ivar y: Raw Y values associated with the channel.
    @ivar kind: Channel kind: time, Bode magnitude, or Bode phase.
    @ivar source_file: Original file path used to create the channel.
    """
    name: str
    x: np.ndarray
    y: np.ndarray
    kind: ChannelKind
    source_file: str


@dataclass
class ChannelControls:
    """
    @brief Container for Tkinter variables that control one channel.

    @ivar enabled: Controls whether the channel is visible.
    @ivar scale_y: Multiplicative Y scale entered as text.
    @ivar offset_y: Additive Y offset entered as text.
    @ivar offset_x: Additive X offset for time-domain channels.
    @ivar color: HEX color used for plotting the channel.
    """
    enabled: tk.BooleanVar
    scale_y: tk.StringVar
    offset_y: tk.StringVar
    offset_x: tk.StringVar
    color: tk.StringVar


@dataclass
class CursorItem:
    """
    @brief Container for one user-defined cursor.

    @ivar cursor_id: Numeric identifier shown in the cursor table.
    @ivar channel: Channel followed by this cursor.
    @ivar x: Displayed X coordinate of the cursor.
    @ivar y: Displayed Y coordinate computed by interpolation.
    @ivar color: Color used to draw the cursor.
    """
    cursor_id: int
    channel: str
    x: float
    y: float
    color: str
