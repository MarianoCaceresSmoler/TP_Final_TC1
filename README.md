# Trabajo Práctico Final - Teoría de Circuitos I

## Descripción general

Este proyecto corresponde al Trabajo Práctico Final de la materia **Teoría de Circuitos I**. El trabajo integra simulación, medición, análisis teórico, desarrollo de software y diseño de PCB.

El proyecto se divide en cuatro partes principales:

1. Desarrollo de una GUI en Python para graficar y analizar archivos CSV.
2. Análisis transitorio de un circuito RLC.
3. Estudio de filtros pasivos de segundo orden.
4. Diseño, simulación, fabricación y medición de un filtro pasabanda para señales de voz humana.

---

## Objetivos del proyecto

Los objetivos principales del trabajo son:

- Comparar resultados teóricos, simulados y medidos.
- Analizar respuestas temporales y frecuenciales de circuitos eléctricos.
- Automatizar el procesamiento de mediciones mediante una herramienta propia.
- Diseñar un filtro real, implementarlo físicamente y verificar su funcionamiento.
- Documentar el procedimiento completo de diseño, simulación, medición y comparación.

---

## Estructura del proyecto

Una estructura típica del proyecto es:

```text
TP_Final_TC1/
│
├── informe/
│   ├── main.tex
│   ├── preamble.tex
│   ├── tex/
│   └── figuras/
│
├── presentacion/
│   ├── main.tex
│   └── figuras/
│
├── gui/
│   ├── main.py
│   ├── requirements.txt
│   └── tc1_csv_gui/
│
├── simulaciones/
│   ├── transitorio/
│   ├── filtros_segundo_orden/
│   └── filtro_final/
│
├── mediciones/
│   ├── csv/
│   └── resultados/
│
├── pcb/
│   ├── esquematico/
│   ├── layout/
│   └── gerbers/
│
└── README.md
```


---

## Parte 1: GUI en Python

Se desarrolló una aplicación gráfica en Python para cargar, visualizar y analizar archivos CSV provenientes de mediciones de osciloscopio, simulaciones y diagramas de Bode.

La herramienta permite:

- Cargar CSV con cantidad variable de canales.
- Trabajar en modo temporal o modo Bode.
- Superponer mediciones compatibles.
- Escalar, desplazar y cambiar color por canal.
- Usar cursores con cálculo automático de coordenadas.
- Analizar señales en modo XY/Lissajous.
- Exportar gráficos directamente a PDF.

La documentación específica de esta herramienta se encuentra en el README propio de la GUI.

---

## Parte 2: Análisis transitorio

Se analizó el comportamiento transitorio de un circuito RLC con los valores asignados al grupo.

El análisis incluyó:

- Simulación de tensión y corriente.
- Comparación con el desarrollo teórico.
- Medición experimental en protoboard.
- Cálculo de pseudofrecuencia.
- Cálculo de sobrepico.
- Análisis de un caso ideal con resistencias nulas.
- Montecarlo considerando tolerancias de componentes.

Las tolerancias usadas en el análisis Montecarlo fueron:

- Resistencias: 5 %.
- Capacitores: 10 %.
- Inductor: 0 %.

---

## Parte 3: Filtros de segundo orden

Se estudiaron distintas configuraciones pasivas RLC de segundo orden.

Para cada circuito se determinó:

- Tipo de filtro.
- Función transferencia.
- Frecuencia característica.
- Factor de calidad.
- Ancho de banda.
- Polos y ceros.
- Respuesta en frecuencia.
- Comparación entre teoría, simulación y medición.

Los filtros considerados incluyen:

- Pasabajos.
- Pasaaltos.
- Pasabanda.
- Rechazo de banda.

---

## Parte 4: Diseño del filtro final

Se diseñó un filtro pasabanda destinado a conservar la banda útil de voz humana.

El diseño adoptado se basó en etapas RC pasivas desacopladas mediante buffers con operacional. La elección buscó obtener un circuito realizable físicamente, estable y sencillo de medir.

La banda objetivo se tomó aproximadamente como:

```text
300 Hz a 3.4 kHz
```

El diseño final se verificó mediante:

- Cálculo teórico de la función transferencia.
- Simulación en LTspice.
- Diagrama de polos y ceros.
- Medición en protoboard.
- Medición sobre la PCB.
- Comparación entre simulación y medición.

---

## Herramientas utilizadas

Durante el desarrollo del proyecto se utilizaron las siguientes herramientas:

- Python.
- Tkinter.
- NumPy.
- Pandas.
- Matplotlib.
- LTspice.
- LaTeX.
- Beamer.
- Altium Designer u otra herramienta de diseño PCB.
- Osciloscopio digital.
- Generador de funciones.
- Multímetro.

---

## Instalación general

Para trabajar con el proyecto se recomienda tener instalado:

- Python 3.10 o superior.
- Una distribución LaTeX.
- LTspice.
- Git.
- Las dependencias de la GUI indicadas en su README.

Para instalar las dependencias de Python:

```bash
python -m pip install -r gui/requirements.txt
```

---

## Compilación del informe

Desde la carpeta del informe:

```bash
pdflatex main.tex
```

O, si se usa `latexmk`:

```bash
latexmk -pdf main.tex
```

---

## Compilación de la presentación

Desde la carpeta de la presentación:

```bash
pdflatex main.tex
```

O:

```bash
latexmk -pdf main.tex
```

---


## Autores

Trabajo realizado para la materia **Teoría de Circuitos I**.

Grupo 8:

- Mariano Cáceres Smoler.
- Tomás Francisco Castro.
- Jorge López Arauz.
- Lucca Nehuen Yaggi.

---
