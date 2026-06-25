#!/bin/bash

set -e

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo "Cleaning previous builds..."
rm -rf build dist *.spec

echo "Building Linux executable..."
python -m PyInstaller \
  --clean \
  --noconfirm \
  --onefile \
  --collect-all tkinterdnd2 \
  --collect-all matplotlib \
  --hidden-import=tkinter \
  --hidden-import=PIL._tkinter_finder \
  --name graficador_tc1 \
  main.py

echo "Done."
echo "Executable created at: dist/graficador_tc1"