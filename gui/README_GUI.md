# GUI TC1 - Graficador de CSV

## Descripción

Esta aplicación es una herramienta gráfica desarrollada en Python para visualizar y analizar archivos CSV provenientes de mediciones de osciloscopio, simulaciones y diagramas de Bode.

Fue desarrollada para el Trabajo Práctico Final de **Teoría de Circuitos I** y permite comparar mediciones reales, simulaciones de LTspice y resultados teóricos sin tener que reprocesar manualmente los datos.

---

## Funciones principales

La GUI incluye las siguientes funciones:

- Carga de archivos CSV.
- Soporte para cantidad variable de canales.
- Drag & drop de archivos.
- Modo exclusivo de trabajo: temporal o Bode.
- Superposición de varios CSV compatibles.
- Rechazo de archivos inválidos sin cerrar la aplicación.
- Edición individual de cada canal.
- Cursores interactivos.
- Modo XY/Lissajous.
- Exportación directa a PDF.

---

## Modos de trabajo

### Modo temporal

El modo temporal se utiliza para señales medidas o simuladas en función del tiempo.

Permite:

- Graficar tensión, corriente u otras variables contra el tiempo.
- Alinear automáticamente cada CSV a `t = 0`.
- Cambiar la unidad del eje X entre segundos, milisegundos, microsegundos y nanosegundos.
- Cambiar la unidad del eje Y entre volts y milivolts.
- Superponer varios archivos temporales.
- Desplazar señales horizontalmente para comparar fases o retardos.

---

### Modo Bode

El modo Bode se activa automáticamente cuando el archivo cargado contiene datos de frecuencia.

Permite:

- Graficar magnitud en dB.
- Graficar fase en grados.
- Usar frecuencia en escala logarítmica.
- Superponer varios diagramas de Bode.
- Comparar simulaciones y mediciones en frecuencia.
- Utilizar cursores sobre magnitud o fase.

---

### Modo XY / Lissajous

El modo XY permite graficar una señal en función de otra, en lugar de graficarlas en función del tiempo.

Este modo sirve para:

- Comparar dos señales temporales.
- Visualizar desfases.
- Obtener figuras de Lissajous.
- Analizar relación entre entrada y salida.

Para usarlo se debe seleccionar un canal para el eje X y otro canal para el eje Y.

---

## Edición por canal

Cada canal cargado puede configurarse de manera independiente.

Las opciones disponibles son:

- Activar o desactivar visibilidad.
- Cambiar color.
- Cambiar escala vertical.
- Agregar offset vertical.
- Agregar offset horizontal.
- Resetear los parámetros del canal.

El offset horizontal se puede modificar de tres maneras:

1. Escribiendo el valor manualmente.
2. Arrastrando el canal con el mouse.
3. Usando las flechas del teclado.

---

## Cursores

La herramienta incluye cursores interactivos para analizar valores puntuales de las señales.

Funciones de los cursores:

- Agregar varios cursores por canal.
- Ingresar una coordenada X y calcular automáticamente la coordenada Y.
- Mostrar línea vertical y horizontal.
- Mover cursores con mouse.
- Mover cursores con teclado.
- Actualizar la posición escribiendo una coordenada.
- Comparar cursores mediante `ΔX` y `ΔY`.

En modo Bode, los cursores funcionan sobre la magnitud o la fase según el canal seleccionado.

---

## Máximos y mínimos

En modo temporal se pueden marcar automáticamente:

- Máximos.
- Mínimos.

Esto permite identificar rápidamente picos, sobrepicos y valores extremos de la señal.

---

## Exportación a PDF

La GUI permite exportar el gráfico actual como archivo PDF.

El PDF exportado incluye:

- Gráfico actual.
- Canales visibles.
- Modo utilizado.
- Nombre de los archivos cargados.
- Fecha y hora de exportación.

---

## Requisitos

Para ejecutar la aplicación se necesita Python 3 y las siguientes librerías:

```text
pandas
numpy
matplotlib
```

Para habilitar drag & drop se recomienda instalar también:

```text
tkinterdnd2
```

En Linux puede ser necesario instalar Tkinter desde el gestor de paquetes del sistema.

Por ejemplo, en distribuciones basadas en Debian o Ubuntu:

```bash
sudo apt install python3-tk
```

---

## Instalación

Desde la carpeta del proyecto de la GUI:

```bash
python -m pip install -r requirements.txt
```

Si se usa Linux y se quiere trabajar dentro de un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

---

## Ejecución

Desde la carpeta del proyecto:

```bash
python main.py
```

También se puede ejecutar como módulo:

```bash
python -m tc1_csv_gui
```

---

## Crear ejecutable en Windows

Primero instalar PyInstaller:

```powershell
py -m pip install pyinstaller
```

Luego ejecutar:

```powershell
py -m PyInstaller --clean --noconfirm --onefile --windowed --collect-all tkinterdnd2 --collect-all matplotlib --name Graficador_TC1 main.py
```

El ejecutable queda en:

```text
dist/Graficador_TC1.exe
```

```powershell
py -m PyInstaller --clean --noconfirm --onefile --collect-all tkinterdnd2 --collect-all matplotlib --name Graficador_TC1 main.py
```

---

## Crear ejecutable en Linux

Primero instalar Tkinter si no está disponible:

```bash
sudo apt install python3-tk
```

Luego crear un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

Compilar con PyInstaller:

```bash
python -m PyInstaller --clean --noconfirm --onefile --collect-all tkinterdnd2 --collect-all matplotlib --hidden-import=tkinter --hidden-import=PIL._tkinter_finder --name graficador_tc1 main.py
```

El ejecutable queda en:

```text
dist/graficador_tc1
```

Para ejecutarlo:

```bash
./dist/graficador_tc1
```

Si se desea ocultar la consola, se puede agregar `--windowed`, pero para depurar errores conviene no usarlo.

---

## Estructura del proyecto

```text
gui/
│
├── main.py
├── requirements.txt
├── README.md
├── build_windows.bat
├── build_linux.sh
│
└── tc1_csv_gui/
    ├── __init__.py
    ├── __main__.py
    ├── app.py
    ├── common.py
    ├── ui.py
    ├── file_loading.py
    ├── channel_panel.py
    ├── plotting.py
    ├── cursors.py
    ├── time_shift.py
    ├── exporting.py
    └── misc.py
```

---



## Problemas comunes

### El programa no abre en Linux

Verificar que Tkinter esté instalado:

```bash
sudo apt install python3-tk
```

También conviene ejecutar el programa desde terminal para ver el error:

```bash
python main.py
```

---

### El ejecutable crashea en Linux

Compilar sin `--windowed` para ver el traceback:

```bash
./dist/graficador_tc1
```

Si hace falta, usar `--onedir` en vez de `--onefile` para detectar dependencias faltantes.

---

### Drag & drop no funciona

Instalar `tkinterdnd2`:

```bash
python -m pip install tkinterdnd2
```

Si no está instalado, la GUI sigue funcionando, pero se desactiva el arrastre de archivos.

---

## Observaciones

La herramienta fue pensada para facilitar la comparación entre mediciones reales y simulaciones. Permite evitar tareas repetitivas de procesamiento manual y mejora la trazabilidad de los gráficos usados en el informe y la presentación.
