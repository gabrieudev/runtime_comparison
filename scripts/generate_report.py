#!/usr/bin/env python3
from pathlib import Path
import sys
import json
import math
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from matplotlib.ticker import FuncFormatter

# --- Configuração visual ---
DPI = 300
plt.rcParams.update({
    'figure.dpi': DPI,
    'savefig.dpi': DPI,
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial'],
    'font.size': 10,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'legend.title_fontsize': 11,
    'figure.titlesize': 16,
})

# Cores dos runtimes
RUNTIME_COLORS = {
    'bun': '#00aaff',
    'deno': '#00cc88', 
    'node': '#ff6b6b'
}

# -------------------------- utilitários --------------------------

def ic95(arr):
    a = np.array(arr, dtype=float)
    a = a[~np.isnan(a)]
    n = a.size
    if n <= 1:
        return 0.0
    se = a.std(ddof=1) / math.sqrt(n)
    h = se * stats.t.ppf((1 + 0.95) / 2., n-1)
    return float(h)


def _parse_iso_to_epoch_seconds(s: str):
    if not s:
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1]
    if '.' in s:
        date_part, frac = s.split('.', 1)
        frac_digits = ''.join(ch for ch in frac if ch.isdigit())
        frac6 = (frac_digits + "000000")[:6]
        s2 = f"{date_part}.{frac6}"
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(s2)
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    else:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(s)
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    try:
        from dateutil import parser as _parser
        dt = _parser.parse(s)
        if dt.tzinfo is None:
            from datetime import timezone
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None

# ---------------------------- parsing k6 ----------------------------

def parse_k6_json(path):
    def extract_metrics_dict(j):
        m = j.get('metrics') if isinstance(j, dict) else None
        if m and isinstance(m, dict):
            out = {}
            hrd = m.get('http_req_duration')
            if hrd:
                out['lat_mean'] = hrd.get('avg') or hrd.get('mean') or None
                out['lat_p95'] = hrd.get('p(95)') or hrd.get('p95') or None
            hrs = m.get('http_reqs')
            if hrs:
                out['http_reqs_count'] = hrs.get('count') or hrs.get('sum') or None
            dr = m.get('data_received')
            if dr:
                out['data_received'] = dr.get('count') or dr.get('sum') or None
            ds = m.get('data_sent')
            if ds:
                out['data_sent'] = ds.get('count') or ds.get('sum') or None
            return out
        return None

    try:
        with open(path, 'r') as f:
            j = json.load(f)
        if isinstance(j, list):
            for item in reversed(j):
                d = extract_metrics_dict(item)
                if d:
                    return d
        else:
            d = extract_metrics_dict(j)
            if d:
                return d
    except Exception:
        pass

    dur_vals = []
    req_counts = 0.0
    data_received = 0.0
    data_sent = 0.0
    times = []

    try:
        with open(path, 'r') as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    d = obj.get('data')
                    if isinstance(d, dict):
                        ts_str = d.get('time') or d.get('timestamp') or None
                        if ts_str:
                            ts = _parse_iso_to_epoch_seconds(ts_str)
                            if ts is not None:
                                times.append(ts)
                metric = obj.get('metric') or (obj.get('data') or {}).get('name')
                typ = obj.get('type') or obj.get('t') or None
                if typ and isinstance(typ, str) and typ.lower() == 'point':
                    val = None
                    d = obj.get('data', {})
                    if isinstance(d, dict):
                        val = d.get('value')
                    try:
                        if val is not None:
                            val = float(val)
                    except Exception:
                        val = None
                    if metric == 'http_req_duration' and val is not None:
                        dur_vals.append(val)
                    elif metric == 'http_reqs' and val is not None:
                        req_counts += float(val)
                    elif metric == 'data_received' and val is not None:
                        data_received += float(val)
                    elif metric == 'data_sent' and val is not None:
                        data_sent += float(val)
    except Exception:
        pass

    out = {}
    if dur_vals:
        arr = np.array(dur_vals, dtype=float)
        out['lat_mean'] = float(arr.mean())
        out['lat_p95'] = float(np.percentile(arr, 95))
    if req_counts:
        out['http_reqs_count'] = float(req_counts)
    if data_received:
        out['data_received'] = float(data_received)
    if data_sent:
        out['data_sent'] = float(data_sent)

    if times:
        try:
            duration = max(times) - min(times)
            if duration > 0:
                out['observed_duration_sec'] = float(duration)
                if out.get('http_reqs_count') is not None:
                    out['throughput_rps'] = out['http_reqs_count'] / duration
        except Exception:
            pass

    return out

# ------------------------- parsing monitor.csv -------------------------

def parse_monitor_csv(path):
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if 'timestamp' not in df.columns:
        return None
    cpu_col = None
    for candidate in ['cpu_percent','CPU','cpu','cpu%']:
        if candidate in df.columns:
            cpu_col = candidate
            break
    if cpu_col is None:
        if df.shape[1] >= 2:
            cpu_col = df.columns[1]
        else:
            return None
    def to_num(x):
        try:
            s = str(x).strip().replace('%','').replace('"','')
            return float(s)
        except Exception:
            return np.nan
    df['cpu_num'] = df[cpu_col].apply(to_num)
    try:
        start = float(df['timestamp'].min())
        end = float(df['timestamp'].max())
        duration = max(1.0, end - start)
    except Exception:
        duration = None
    cpu_mean = float(df['cpu_num'].mean()) if not df['cpu_num'].dropna().empty else None
    return {'cpu_mean': cpu_mean, 'duration': duration, 'df': df}

# ------------------------- coleta/agregação -------------------------

def collect(results_root):
    rows = []
    results_root = Path(results_root)
    if not results_root.exists():
        raise FileNotFoundError(f"{results_root} não encontrado")
    for runtime_dir in sorted(results_root.iterdir()):
        if not runtime_dir.is_dir():
            continue
        runtime = runtime_dir.name
        for vus_dir in sorted(runtime_dir.iterdir()):
            if not vus_dir.is_dir():
                continue
            vus_str = vus_dir.name.replace('vus_', '')
            try:
                vus = int(vus_str)
            except Exception:
                vus = vus_str
            for rep_dir in sorted(vus_dir.iterdir()):
                if not rep_dir.is_dir():
                    continue
                rep_str = rep_dir.name.replace('rep_','')
                try:
                    rep = int(rep_str)
                except Exception:
                    rep = rep_str
                k6_files = list(rep_dir.glob('k6_*.json'))
                k6m = {}
                if k6_files:
                    try:
                        k6m = parse_k6_json(str(k6_files[0]))
                    except Exception:
                        k6m = {}
                monitor_file = rep_dir / 'monitor.csv'
                monitorm = {}
                if monitor_file.exists():
                    try:
                        monitorm = parse_monitor_csv(str(monitor_file))
                    except Exception:
                        monitorm = {}
                row = {
                    'runtime': runtime,
                    'vus': vus,
                    'rep': rep,
                    'k6': k6m,
                    'monitor': monitorm,
                    'raw_dir': str(rep_dir)
                }
                rows.append(row)
    return rows


def aggregate(rows):
    records = []
    for r in rows:
        k6 = r.get('k6') or {}
        monitor = r.get('monitor') or {}
        rec = {
            'runtime': r['runtime'],
            'vus': r['vus'],
            'rep': r['rep'],
            'lat_mean': k6.get('lat_mean'),
            'lat_p95': k6.get('lat_p95'),
            'http_reqs_count': k6.get('http_reqs_count'),
            'data_received': k6.get('data_received'),
            'data_sent': k6.get('data_sent'),
            'cpu_mean': monitor.get('cpu_mean') if isinstance(monitor, dict) else None,
            'duration_sec': monitor.get('duration') if isinstance(monitor, dict) else None,
            'raw_dir': r['raw_dir']
        }
        for k in ['lat_mean','lat_p95','http_reqs_count','data_received','data_sent','cpu_mean','duration_sec']:
            try:
                if rec[k] is not None:
                    rec[k] = float(rec[k])
            except Exception:
                rec[k] = np.nan
        if (not math.isnan(rec.get('http_reqs_count') or float('nan'))) and rec.get('duration_sec'):
            rec['throughput_rps'] = rec['http_reqs_count'] / max(1.0, rec['duration_sec'])
        else:
            rec['throughput_rps'] = np.nan
        records.append(rec)
    df = pd.DataFrame.from_records(records)
    return df


def summarize(df):
    agg_rows = []
    grouped = df.groupby(['runtime','vus'])
    for (runtime,vus), g in grouped:
        entry = {
            'runtime': runtime,
            'vus': int(vus) if pd.notna(vus) else vus,
            'n_reps': int(g['rep'].nunique()),
            'lat_p95_mean': float(g['lat_p95'].dropna().mean()) if not g['lat_p95'].dropna().empty else np.nan,
            'lat_p95_ic95': float(ic95(g['lat_p95'].dropna().values)) if not g['lat_p95'].dropna().empty else 0.0,
            'lat_mean_mean': float(g['lat_mean'].dropna().mean()) if not g['lat_mean'].dropna().empty else np.nan,
            'lat_mean_ic95': float(ic95(g['lat_mean'].dropna().values)) if not g['lat_mean'].dropna().empty else 0.0,
            'throughput_mean': float(g['throughput_rps'].dropna().mean()) if not g['throughput_rps'].dropna().empty else np.nan,
            'throughput_ic95': float(ic95(g['throughput_rps'].dropna().values)) if not g['throughput_rps'].dropna().empty else 0.0,
            'cpu_mean': float(g['cpu_mean'].dropna().mean()) if not g['cpu_mean'].dropna().empty else np.nan,
            'cpu_ic95': float(ic95(g['cpu_mean'].dropna().values)) if not g['cpu_mean'].dropna().empty else 0.0
        }
        agg_rows.append(entry)
    out = pd.DataFrame.from_records(agg_rows)
    out = out.sort_values(['runtime','vus'])
    return out

# ------------------------- funções de plotagem -------------------------

def _fmt_thousands(x, pos):
    """Formata números para usar separador de milhar (ponto)"""
    try:
        xi = int(round(x))
        if abs(xi) >= 1000:
            return f"{xi:,}".replace(',', '.')
        return str(xi)
    except Exception:
        return f"{x:.0f}"


def _fmt_decimal(x, pos):
    """Formata números decimais com 1 casa decimal"""
    return f"{x:.1f}"


def plot_grouped_bars(summary_df, metric_col, ic_col, out_stem, ylabel, title, 
                     annotate_vals=True, thousands_formatter=True, log_scale=False):
    Path(out_stem).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        vus_levels = sorted(pd.to_numeric(summary_df['vus'], errors='coerce').dropna().unique().astype(int))
    except Exception:
        vus_levels = sorted(summary_df['vus'].unique())
    
    runtimes = sorted(summary_df['runtime'].unique())
    n_vus = len(vus_levels)
    n_runtime = len(runtimes)
    
    # Ajuste dinâmico do tamanho da figura baseado no número de VUs
    fig_width = max(10, n_vus * 2.5)
    fig_height = 6
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), constrained_layout=True)
    
    x = np.arange(n_vus)
    width = 0.8 / max(1, n_runtime)  # Largura das barras
    
    # Plotagem das barras para cada runtime
    for i, runtime in enumerate(runtimes):
        vals = []
        errs = []
        for vus in vus_levels:
            row = summary_df[(summary_df['runtime'] == runtime) & (summary_df['vus'] == vus)]
            if not row.empty:
                val = pd.to_numeric(row.iloc[0][metric_col], errors='coerce')
                err = pd.to_numeric(row.iloc[0][ic_col], errors='coerce')
                vals.append(float(np.nan_to_num(val, nan=0.0)))
                errs.append(float(np.nan_to_num(err, nan=0.0)))
            else:
                vals.append(0.0)
                errs.append(0.0)

        vals = np.array(vals, dtype=float)
        errs = np.array(errs, dtype=float)

        # Barras com erro
        color = RUNTIME_COLORS.get(runtime.lower(), f'C{i}')
        bars = ax.bar(x + i*width, vals, width, 
                     yerr=errs, label=runtime, color=color, alpha=0.85,
                     capsize=5, error_kw=dict(ecolor='black', lw=1.0, capsize=3))

        # Anotações dos valores
        if annotate_vals:
            for j, bar in enumerate(bars):
                h = bar.get_height()
                if h > 0:  # Só anota se o valor for maior que zero
                    err_val = errs[j]
                    
                    # Posicionamento inteligente da anotação
                    y_pos = h + err_val + (0.02 * ax.get_ylim()[1])
                    
                    # Formatação do texto baseada no tipo de métrica
                    if thousands_formatter and h >= 1000:
                        text = f"{h:,.0f}".replace(',', '.')
                    elif metric_col in ['cpu_mean']:
                        text = f"{h:.1f}%"
                    elif h < 10:
                        text = f"{h:.1f}"
                    else:
                        text = f"{h:.0f}"
                    
                    ax.annotate(text, 
                               xy=(bar.get_x() + bar.get_width()/2, y_pos),
                               xytext=(0, 2), textcoords='offset points',
                               ha='center', va='bottom', fontsize=9, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.2', fc='white', 
                                       ec='gray', alpha=0.8, lw=0.5))

    # Configurações do eixo X
    ax.set_xticks(x + width*(n_runtime-1)/2)
    ax.set_xticklabels([f"{v} VUs" for v in vus_levels])
    ax.set_xlabel('VUs (usuários concorrentes)', fontweight='bold')
    ax.set_ylabel(ylabel, fontweight='bold')
    
    # Título e legenda
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    leg = ax.legend(frameon=True, framealpha=0.9, 
                   bbox_to_anchor=(1.02, 1), loc='upper left')
    leg.set_title('Runtime', prop={'weight': 'bold'})
    
    # Grade
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    ax.set_axisbelow(True)
    
    # Escala logarítmica
    if log_scale:
        ax.set_yscale('log')
    
    # Formatação do eixo Y
    if thousands_formatter:
        ax.yaxis.set_major_formatter(FuncFormatter(_fmt_thousands))
    elif metric_col in ['cpu_mean']:
        ax.yaxis.set_major_formatter(FuncFormatter(_fmt_decimal))
    
    # Ajuste automático dos limites do eixo Y para acomodar anotações
    y_max = ax.get_ylim()[1]
    ax.set_ylim(0, y_max * 1.15)

    # Salvar apenas PNG
    p = Path(out_stem).with_suffix('.png')
    fig.savefig(p, bbox_inches='tight', dpi=DPI, facecolor='white')
    plt.close(fig)
    print(f"Gráfico salvo: {p}")

# ------------------------- geração do relatório -------------------------

def generate(results_root):
    print("Coletando resultados em:", results_root)
    rows = collect(results_root)
    if not rows:
        print("Nenhum resultado encontrado em", results_root)
        return
    df = aggregate(rows)
    summary = summarize(df)

    out_dir = Path(results_root) / 'plots'
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = Path(results_root) / 'results_summary.csv'
    summary.to_csv(summary_csv, index=False)
    print("Resumo salvo em:", summary_csv)

    # Gerar gráficos de barras para todas as métricas
    plot_grouped_bars(summary, 'lat_p95_mean', 'lat_p95_ic95', 
                     str(out_dir / 'latencia_p95'), 
                     ylabel='Latência p95 (ms)', 
                     title='Latência p95 por Runtime e VUs',
                     thousands_formatter=False)
    
    plot_grouped_bars(summary, 'lat_mean_mean', 'lat_mean_ic95', 
                     str(out_dir / 'latencia_media'), 
                     ylabel='Latência média (ms)', 
                     title='Latência Média por Runtime e VUs',
                     thousands_formatter=False)
    
    plot_grouped_bars(summary, 'throughput_mean', 'throughput_ic95', 
                     str(out_dir / 'throughput'), 
                     ylabel='Requisições por segundo (req/s)', 
                     title='Throughput por Runtime e VUs',
                     thousands_formatter=True)
    
    plot_grouped_bars(summary, 'cpu_mean', 'cpu_ic95', 
                     str(out_dir / 'cpu_media'), 
                     ylabel='CPU média (%)', 
                     title='Uso de CPU Médio por Runtime e VUs',
                     thousands_formatter=False)

    print("\n" + "="*60)
    print("RELATÓRIO GERADO COM SUCESSO!")
    print("="*60)
    print(f"Gráficos individuais salvos em: {out_dir}")
    print(f"Dados sumarizados: {summary_csv}")
    print("="*60)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: generate_report.py <diretório_results>")
        sys.exit(1)
    generate(sys.argv[1])