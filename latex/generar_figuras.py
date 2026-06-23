from __future__ import annotations
import re, os, math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(__file__).parent
FIG = BASE / 'figuras'
DAT = BASE / 'data'
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    'figure.dpi': 120,
    'savefig.dpi': 300,
    'font.size': 10,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'legend.fontsize': 8,
})

R = 50.0
L = 1e-3
C = 82e-9

def read_scope_time(path: Path):
    # expected first two rows are headers/units
    df = pd.read_csv(path, skiprows=2, header=None, encoding='latin1')
    return df.iloc[:,0].to_numpy(float), df.iloc[:,1].to_numpy(float)

def read_time_any(path: Path):
    try:
        df = pd.read_csv(path, sep='\t', encoding='latin1')
        if df.shape[1] >= 2:
            return df.iloc[:,0].to_numpy(float), df.iloc[:,1].to_numpy(float)
    except Exception:
        pass
    try:
        df = pd.read_csv(path, encoding='latin1')
        nums = df.apply(pd.to_numeric, errors='coerce').dropna(how='all').dropna(axis=1, how='all')
        return nums.iloc[:,0].to_numpy(float), nums.iloc[:,1].to_numpy(float)
    except Exception:
        return read_scope_time(path)

def parse_bode_cell(cell):
    s = str(cell).strip().strip('"').strip("'").strip()
    s = s.strip('()')
    parts = [p.strip() for p in s.split(',')]
    mag = float(parts[0].lower().replace('db','').replace('°','').strip())
    ph = np.nan
    if len(parts) > 1:
        ph_txt = parts[1].replace('°','').replace('\\xb0','').strip()
        try: ph = float(ph_txt)
        except Exception: ph = np.nan
    return mag, ph

def read_bode_lt(path: Path):
    df = pd.read_csv(path, sep='\t', encoding='latin1')
    f = pd.to_numeric(df.iloc[:,0], errors='coerce').to_numpy(float)
    mags=[]; phs=[]
    for c in df.iloc[:,1]:
        m,p = parse_bode_cell(c)
        mags.append(m); phs.append(p)
    return f, np.array(mags,float), np.array(phs,float)

def read_bode_named(path: Path):
    df = pd.read_csv(path, encoding='latin1')
    # strip spaces in columns
    cols = {c: c.strip().lower() for c in df.columns}
    freq_col = next(c for c,l in cols.items() if 'frequency' in l or 'freq' in l)
    gain_col = next(c for c,l in cols.items() if 'gain' in l or 'db' in l)
    phase_col = next((c for c,l in cols.items() if 'phase' in l or 'fase' in l), None)
    f = pd.to_numeric(df[freq_col], errors='coerce').to_numpy(float)
    g = pd.to_numeric(df[gain_col], errors='coerce').to_numpy(float)
    p = pd.to_numeric(df[phase_col], errors='coerce').to_numpy(float) if phase_col is not None else np.full_like(f, np.nan)
    return f,g,p

def read_bode(path: Path):
    with open(path, 'r', encoding='utf-8-sig', errors='ignore') as fh:
        head = fh.readline()
        line = fh.readline()
    if head.lower().startswith('freq') and '(' in line:
        return read_bode_lt(path)
    return read_bode_named(path)

def first_peak_time(t, y, polarity=1, min_frac=0.75):
    yy = polarity*y
    m = np.nanmax(yy)
    threshold = min_frac*m
    # first local max above threshold
    for i in range(1, len(yy)-1):
        if yy[i] > threshold and yy[i] >= yy[i-1] and yy[i] >= yy[i+1]:
            return t[i]
    return t[int(np.nanargmax(yy))]

# 1) Transient aligned
try:
    to, yo = read_scope_time(DAT/'2_1_osciloscopio(1).csv')
    ts, ys = read_time_any(DAT/'2_1_simulado(1).csv')
except FileNotFoundError:
    to, yo = read_scope_time(DAT/'2_1_osciloscopio.csv')
    ts, ys = read_time_any(DAT/'2_1_simulado.csv')
# make osc start at 0, sim start at 0
xto = to - to[np.isfinite(to)][0]
xts = ts - ts[np.isfinite(ts)][0]
# align first positive peak
p_to = first_peak_time(xto, yo, 1, 0.85)
p_ts = first_peak_time(xts, ys, 1, 0.85)
shift = p_to - p_ts
x_sim_us = (xts + shift)*1e6
x_osc_us = xto*1e6
fig, ax = plt.subplots(figsize=(9,5))
ax.plot(x_sim_us, ys, label='LTspice - $V_o$', lw=1.5)
ax.plot(x_osc_us, yo, label='Osciloscopio - $V_o$', lw=1.2)
ax.set_xlabel('Tiempo [µs]')
ax.set_ylabel('Tensión [V]')
ax.set_title('Transitorio: medición y simulación alineadas')
ax.legend(loc='best')
ax.set_xlim(max(0, min(np.nanmin(x_osc_us), np.nanmin(x_sim_us))), min(520, max(np.nanmax(x_osc_us), np.nanmax(x_sim_us))))
fig.tight_layout()
fig.savefig(FIG/'transitorio_2_1.pdf')
fig.savefig(FIG/'transitorio_2_1.png')
plt.close(fig)

# 2) Bode circuit 2 measured vs sim
for stem, sim_file, osc_file, out, title in [
    ('c2', '2_2_2_simulado(1).csv', '2_2_2_osciloscopio.csv', 'bode_circuito2.pdf', 'Circuito 2 - pasabajos'),
    ('c5', '2_2_5_simuladoCONrl.csv', '2_2_5_osciloscopio.csv', 'bode_circuito5.pdf', 'Circuito 5 - rechazo de banda'),
]:
    f1,g1,p1 = read_bode(DAT/sim_file)
    f2,g2,p2 = read_bode(DAT/osc_file)
    fig, (ax1, ax2) = plt.subplots(2,1, figsize=(8,6), sharex=True)
    ax1.semilogx(f1, g1, label='LTspice')
    ax1.semilogx(f2, g2, 'o-', markersize=3, label='Osciloscopio')
    ax1.set_ylabel('Magnitud [dB]')
    ax1.set_title(title)
    ax1.legend()
    ax2.semilogx(f1, p1, label='LTspice')
    ax2.semilogx(f2, p2, 'o-', markersize=3, label='Osciloscopio')
    ax2.set_xlabel('Frecuencia [Hz]')
    ax2.set_ylabel('Fase [°]')
    ax2.legend()
    fig.tight_layout()
    fig.savefig(FIG/out)
    plt.close(fig)

# 3) Bode final filter comparison
f_sim,g_sim,p_sim = read_bode(DAT/'bodeFiltroFinalsimulado(1).csv')
f_pr,g_pr,p_pr = read_bode(DAT/'bodeFiltroRealProtoboard.csv')
f_pl,g_pl,p_pl = read_bode(DAT/'bodeFiltroRealPlaca.csv')
fig, (ax1, ax2) = plt.subplots(2,1, figsize=(8,6), sharex=True)
ax1.semilogx(f_sim, g_sim, label='Simulación')
ax1.semilogx(f_pr, g_pr, 'o-', markersize=3, label='Protoboard')
ax1.semilogx(f_pl, g_pl, 's-', markersize=3, label='Placa')
ax1.axvspan(300, 3400, color='gray', alpha=0.10, label='Banda objetivo')
ax1.set_title('Filtro final para voz humana')
ax1.set_ylabel('Magnitud [dB]')
ax1.legend(loc='best')
ax2.semilogx(f_sim, p_sim, label='Simulación')
ax2.semilogx(f_pr, p_pr, 'o-', markersize=3, label='Protoboard')
ax2.semilogx(f_pl, p_pl, 's-', markersize=3, label='Placa')
ax2.set_xlabel('Frecuencia [Hz]')
ax2.set_ylabel('Fase [°]')
ax2.legend(loc='best')
fig.tight_layout()
fig.savefig(FIG/'bode_filtro_final.pdf')
plt.close(fig)

# 4) theoretical bode of circuits 2-5
w = 2*np.pi*np.logspace(1,6,2000)
s = 1j*w
H2 = 1/(s*s*L*C + s*R*C + 1)
H3 = (s*s*L*C)/(s*s*L*C + s*R*C + 1)
H4 = (s*R*C)/(s*s*L*C + s*R*C + 1)
H5 = (s*s*L*C + 1)/(s*s*L*C + s*R*C + 1)
Hs = {'Circuito 2 - PB':H2, 'Circuito 3 - PA':H3, 'Circuito 4 - PBanda':H4, 'Circuito 5 - Rechazo':H5}
fig, ax = plt.subplots(figsize=(9,5))
for label,H in Hs.items():
    ax.semilogx(w/(2*np.pi), 20*np.log10(np.abs(H)), label=label)
ax.set_xlabel('Frecuencia [Hz]')
ax.set_ylabel('Magnitud [dB]')
ax.set_title('Respuestas teóricas de los circuitos de segundo orden')
ax.legend(loc='best')
ax.set_ylim(-60,10)
fig.tight_layout(); fig.savefig(FIG/'bode_filtros_teoricos.pdf'); plt.close(fig)

# 5) pole-zero diagram
fig, axes = plt.subplots(2,2, figsize=(8,7))
axes = axes.ravel()
w0 = 1/math.sqrt(L*C)
alpha = R/(2*L)
poles = np.roots([1, R/L, 1/(L*C)])
zeros_dict = {
    'Circuito 2': [],
    'Circuito 3': [0,0],
    'Circuito 4': [0],
    'Circuito 5': [1j*w0, -1j*w0],
}
for ax,(name,zeros) in zip(axes, zeros_dict.items()):
    ax.axhline(0,color='k',lw=.6); ax.axvline(0,color='k',lw=.6)
    ax.scatter(np.real(poles), np.imag(poles), marker='x', s=70, label='Polos')
    if zeros:
        ax.scatter(np.real(zeros), np.imag(zeros), marker='o', facecolors='none', edgecolors='C1', s=70, label='Ceros')
    ax.set_title(name)
    ax.set_xlabel('Re(s) [rad/s]')
    ax.set_ylabel('Im(s) [rad/s]')
    lim = 1.2*w0
    ax.set_xlim(-2.2*alpha, 0.25*w0)
    ax.set_ylim(-lim, lim)
    ax.grid(True, alpha=.3)
    ax.legend(loc='best')
fig.tight_layout(); fig.savefig(FIG/'polos_ceros_circuitos.pdf'); plt.close(fig)

# 6) Monte Carlo circuit 5
rng = np.random.default_rng(1)
N=8000
Rmc = R*(1 + rng.normal(0, 0.05/3, N)) # approx 3sigma tolerance
Cmc = C*(1 + rng.normal(0, 0.10/3, N))
Lmc = L*(1 + rng.normal(0, 0.10/3, N))
f0_all = 1/(2*np.pi*np.sqrt(Lmc*Cmc))
Q_all = (1/Rmc)*np.sqrt(Lmc/Cmc)
C_only = C*(1 + rng.normal(0, 0.10/3, N)); f0_C = 1/(2*np.pi*np.sqrt(L*C_only))
L_only = L*(1 + rng.normal(0, 0.10/3, N)); f0_L = 1/(2*np.pi*np.sqrt(L_only*C))
R_only = R*(1 + rng.normal(0, 0.05/3, N)); Q_R = (1/R_only)*np.sqrt(L/C)
fig, axes = plt.subplots(2,2, figsize=(9,7))
axes[0,0].hist(f0_all, bins=60); axes[0,0].set_title('$f_0$ variando R, L y C'); axes[0,0].set_xlabel('Frecuencia [Hz]')
axes[0,1].hist(Q_all, bins=60); axes[0,1].set_title('$Q$ variando R, L y C'); axes[0,1].set_xlabel('Q')
axes[1,0].hist(f0_C, bins=60, alpha=0.65, label='solo C'); axes[1,0].hist(f0_L, bins=60, alpha=0.65, label='solo L'); axes[1,0].set_title('$f_0$ variando una reactancia'); axes[1,0].set_xlabel('Frecuencia [Hz]'); axes[1,0].legend()
axes[1,1].hist(Q_R, bins=60); axes[1,1].set_title('$Q$ variando solo R'); axes[1,1].set_xlabel('Q')
fig.tight_layout(); fig.savefig(FIG/'montecarlo_circuito5.pdf'); plt.close(fig)

# 7) alternative final design comparison: option A/B/final theoretical approximation
f = np.logspace(1,5,2000); s = 1j*2*np.pi*f
# option A: RLC PB L=1m C=2.2u R=30 -> buffer -> RC-RC PA R=15k C=100n
H_A_PB = 1/(s*s*1e-3*2.2e-6 + s*30*2.2e-6 + 1)
H_A_PA = (s*15e3*100e-9)**2/((s*15e3*100e-9)**2+3*s*15e3*100e-9+1)
HA = H_A_PB*H_A_PA
# option B: RLC PB R=300 L=10m C=220n, RLC PA R=270 L=100m C=2.7u
H_B_PB = 1/(s*s*10e-3*220e-9 + s*300*220e-9 + 1)
H_B_PA = (s*s*100e-3*2.7e-6)/(s*s*100e-3*2.7e-6 + s*270*2.7e-6 + 1)
HB = H_B_PB*H_B_PA
# final: RC-RC PB and RC-RC PA
H_F_PB = 1/((s*1.8e3*10e-9)**2 + 3*s*1.8e3*10e-9 + 1)
H_F_PA = (s*15e3*100e-9)**2/((s*15e3*100e-9)**2 + 3*s*15e3*100e-9 + 1)
HF = H_F_PB*H_F_PA
fig, ax = plt.subplots(figsize=(8,5))
for label,H in [('Opción A: RLC + RC',HA),('Opción B: dos RLC',HB),('Diseño final RC',HF)]:
    ax.semilogx(f,20*np.log10(np.abs(H)),label=label)
ax.axvspan(300,3400,color='gray',alpha=.1,label='Banda objetivo')
ax.set_xlabel('Frecuencia [Hz]'); ax.set_ylabel('Magnitud [dB]'); ax.set_title('Comparación de alternativas de filtro')
ax.set_ylim(-60,5); ax.legend(loc='best'); fig.tight_layout(); fig.savefig(FIG/'comparacion_opciones_filtro.pdf'); plt.close(fig)

# simple bode of final theoretical vs simulation maybe already done
print('figures generated in', FIG)
