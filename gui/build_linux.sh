#!/usr/bin/env bash
# @file build_linux.sh
# @brief Build a Linux executable with PyInstaller.

set -e
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --clean --noconfirm --onefile --windowed --collect-all tkinterdnd2 --name graficador_tc1 main.py

echo "Executable generated in: dist/graficador_tc1"
