@echo off
REM @file build_windows.bat
REM @brief Build a Windows .exe with PyInstaller.

py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --clean --noconfirm --onefile --windowed --collect-all tkinterdnd2 --name Graficador_TC1 main.py

echo.
echo EXE generated in: dist\Graficador_TC1.exe
pause
