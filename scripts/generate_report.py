#!/usr/bin/env python3
from pathlib import Path
import sys
import json
import math
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ========================= LOGGING SIMPLES =========================

def _log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level:<5} | {msg}")

def log_info(msg):
    _log("INFO", msg)

def log_warn(msg):
    _log("WARN", msg)

def log_error(msg):
    _log("ERROR", msg)

# ========================= CONFIGURAÇÃO GLOBAL =========================

PNG_DPI = 300
PDF_DPI = 600

plt.rcParams.update({
    'figure.dpi': PNG_DPI,
    'savefig.dpi': PNG_DPI,
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'mathtext.fontset': 'stix',
    'font.size': 11,
    'axes.labelsize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'legend.title_fontsize': 11,
    'figure.constrained_layout.use': True,
})

RUNTIME_COLORS = {
    'bun': '#2E86AB',
    'deno': '#A23B72',
    'node': '#F18F01'
}

I18N = {
    "pt": {
        "vus": "Usuários Virtuais (VUs)",
        "runtime": "Runtime",
        "p95_latency": "Latência p95 (ms)",
        "mean_latency": "Latência Média (ms)",
        "throughput": "Throughput (RPS)",
        "cpu": "Uso Médio de CPU (%)",
        "memory": "Uso Médio de Memória (MB)",
    },
    "en": {
        "vus": "Virtual Users (VUs)",
        "runtime": "Runtime",
        "p95_latency": "p95 Latency (ms)",
        "mean_latency": "Mean Latency (ms)",
        "throughput": "Throughput (RPS)",
        "cpu": "Mean CPU Usage (%)",
        "memory": "Mean Memory Usage (MB)",
    }
}

# ========================= UTILITÁRIOS =========================

def ic95(arr):
    a = np.array(arr, dtype=float)
    a = a[~np.isnan(a)]
    n = a.size
    if n <= 1:
        return 0.0
    se = a.std(ddof=1) / math.sqrt(n)
    return float(se * stats.t.ppf(0.975, n - 1))


def _fmt_thousands(x, _):
    try:
        xi = int(round(x))
        return f"{xi:,}".replace(",", ".") if abs(xi) >= 1000 else str(xi)
    except Exception:
        return ""


def _fmt_decimal(x, _):
    return f"{x:.1f}"

# ========================= PARSING K6 =========================

def parse_k6_json(path: Path):
    if not path or not path.exists():
        log_warn(f"k6_results.json não encontrado: {path}")
        return {}

    durations = []
    reqs = 0

    with open(path, "r") as f:
        for line in f:
            try:
                j = json.loads(line)
            except Exception:
                continue

            if j.get("type") != "Point":
                continue

            metric = j.get("metric")
            val = j.get("data", {}).get("value")

            if metric == "http_req_duration":
                durations.append(val)
            elif metric == "http_reqs":
                reqs += int(val)

    if not durations:
        log_warn(f"Arquivo k6 sem métricas válidas: {path}")
        return {}

    return {
        "lat_mean": float(np.mean(durations)),
        "lat_p95": float(np.percentile(durations, 95)),
        "http_reqs": reqs,
    }

# ========================= MONITOR CSV =========================

def parse_monitor_csv(path: Path):
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log_warn(f"Falha ao ler monitor CSV {path}: {e}")
        return {}

    log_info(f"Lendo monitor: {path.name} | colunas={list(df.columns)}")
    out = {}

    # ================= CPU =================
    if "cpu_percent" in df.columns:
        try:
            df["cpu_percent"] = (
                df["cpu_percent"]
                .astype(str)
                .str.replace("%", "", regex=False)
                .astype(float)
            )
            out["cpu"] = df["cpu_percent"].mean()
            log_info(f"CPU média: {out['cpu']:.2f}%")
        except Exception as e:
            log_warn(f"Erro ao processar CPU: {e}")

    # ================= MEMÓRIA =================
    if "mem_usage_mb" in df.columns:
        try:
            df["mem_usage_mb"] = pd.to_numeric(df["mem_usage_mb"], errors="coerce")
            valid = df["mem_usage_mb"].notna().sum()

            if valid > 0:
                out["memory"] = df["mem_usage_mb"].mean()
                log_info(
                    f"Memória média: {out['memory']:.2f} MB "
                    f"(válidos {valid}/{len(df)})"
                )
            else:
                log_warn("mem_usage_mb sem valores válidos")
        except Exception as e:
            log_warn(f"Erro ao processar mem_usage_mb: {e}")

    elif "mem_usage" in df.columns:
        def parse_mem_to_mib(val):
            try:
                s = str(val).strip().lower()
                if s.endswith("gib"):
                    return float(s.replace("gib", "")) * 1024
                if s.endswith("mib"):
                    return float(s.replace("mib", ""))
                if s.endswith("kib"):
                    return float(s.replace("kib", "")) / 1024
            except Exception:
                return np.nan
            return np.nan

        df["mem_mib"] = df["mem_usage"].apply(parse_mem_to_mib)
        valid = df["mem_mib"].notna().sum()

        if valid > 0:
            out["memory"] = df["mem_mib"].mean()
            log_info(f"Memória média: {out['memory']:.2f} MiB")
        else:
            log_warn("mem_usage presente, mas inválido")

    else:
        log_warn("Nenhuma coluna de memória encontrada")

    # ================= DURAÇÃO =================
    if "timestamp" in df.columns:
        try:
            out["duration"] = df["timestamp"].max() - df["timestamp"].min()
            log_info(f"Duração monitorada: {out['duration']:.2f}s")
        except Exception:
            log_warn("Erro ao calcular duração")

    return out

# ========================= COLETA =========================

def collect(root):
    rows = []
    root = Path(root)

    log_info(f"Coletando dados em: {root}")

    for runtime_dir in root.iterdir():
        if not runtime_dir.is_dir():
            continue

        log_info(f"Runtime detectado: {runtime_dir.name}")

        for vus_dir in runtime_dir.iterdir():
            for rep_dir in vus_dir.iterdir():
                k6 = parse_k6_json(rep_dir / "k6_results.json")
                monitor = parse_monitor_csv(rep_dir / "docker_stats.csv") \
                    if (rep_dir / "docker_stats.csv").exists() else {}

                if not k6 or "duration" not in monitor:
                    log_warn(f"Amostra inválida ignorada: {rep_dir}")
                    continue

                rows.append({
                    "runtime": runtime_dir.name,
                    "vus": int(vus_dir.name.replace("vus_", "")),
                    "lat_mean": k6["lat_mean"],
                    "lat_p95": k6["lat_p95"],
                    "throughput": k6["http_reqs"] / monitor["duration"],
                    "cpu": monitor.get("cpu"),
                    "memory": monitor.get("memory"),
                })

    return pd.DataFrame(rows)

# ========================= AGREGAÇÃO =========================

def summarize(df):
    log_info("Gerando resumo estatístico")
    return df.groupby(["runtime", "vus"]).agg(
        lat_p95_mean=("lat_p95", "mean"),
        lat_p95_ic95=("lat_p95", ic95),
        lat_mean_mean=("lat_mean", "mean"),
        lat_mean_ic95=("lat_mean", ic95),
        throughput_mean=("throughput", "mean"),
        throughput_ic95=("throughput", ic95),
        cpu_mean=("cpu", "mean"),
        cpu_ic95=("cpu", ic95),
        memory_mean=("memory", "mean"),
        memory_ic95=("memory", ic95),
    ).reset_index()

# ========================= PLOT =========================

def plot_grouped_bars(df, metric, ic, out, ylabel, lang, thousands=False):
    runtimes = sorted(df["runtime"].unique())
    vus = sorted(df["vus"].unique())

    fig, ax = plt.subplots(figsize=(max(10, len(vus) * 2.5), 6))

    x = np.arange(len(vus))
    width = 0.8 / len(runtimes)

    bar_containers = []
    err_values = []

    for i, rt in enumerate(runtimes):
        vals, errs = [], []

        for v in vus:
            row = df[(df.runtime == rt) & (df.vus == v)]
            if row.empty:
                vals.append(0)
                errs.append(0)
                continue

            val = max(0.0, float(row[metric].iat[0]))
            err = max(0.0, float(row[ic].iat[0]))
            errs.append(min(err, val) if val > 0 else 0)
            vals.append(val)

        bars = ax.bar(
            x + i * width,
            vals,
            width,
            yerr=errs,
            capsize=5,
            color=RUNTIME_COLORS.get(rt),
            label=rt.capitalize(),
            error_kw=dict(ecolor="black", lw=1),
            alpha=0.85
        )

        bar_containers.append(bars)
        err_values.append(errs)

    ax.set_xticks(x + width * (len(runtimes) - 1) / 2)
    ax.set_xticklabels(vus)
    ax.set_xlabel(I18N[lang]["vus"])
    ax.set_ylabel(ylabel)

    ax.legend(
        title=I18N[lang]["runtime"],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.15),
        ncol=len(runtimes),
        frameon=False
    )

    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)

    ax.yaxis.set_major_formatter(
        FuncFormatter(_fmt_thousands if thousands else _fmt_decimal)
    )

    # ====== RÓTULOS ACIMA DAS BARRAS ======
    fig.canvas.draw()
    y_max = ax.get_ylim()[1]

    for bars, errs in zip(bar_containers, err_values):
        for rect, err in zip(bars, errs):
            h = rect.get_height()
            if h <= 0:
                continue

            y_pos = h + err + (0.02 * y_max)

            label = (
                f"{h:,.0f}".replace(",", ".")
                if thousands
                else f"{h:.1f}"
            )

            ax.annotate(
                label,
                (rect.get_x() + rect.get_width() / 2, y_pos),
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold"
            )

    ax.set_ylim(0, y_max * 1.15)

    out = Path(out)
    fig.savefig(out.with_name(out.name + f"_{lang}.png"), dpi=PNG_DPI)
    fig.savefig(out.with_name(out.name + f"_{lang}.pdf"), dpi=PDF_DPI)
    plt.close(fig)

# ========================= MAIN =========================

def generate(root):
    log_info("Iniciando geração de relatório")

    df = collect(root)
    if df.empty:
        log_error("Nenhum dado coletado. Abortando.")
        return

    log_info(f"Amostras coletadas: {len(df)}")

    summary = summarize(df)
    log_info(
        f"Resumo: {len(summary)} linhas | "
        f"{summary['runtime'].nunique()} runtimes | "
        f"{summary['vus'].nunique()} níveis de VUs"
    )

    out = Path(root) / "plots"
    out.mkdir(exist_ok=True)

    for lang in ("pt", "en"):
        log_info(f"Gerando gráficos ({lang})")
        plot_grouped_bars(summary, "lat_p95_mean", "lat_p95_ic95",
                          out / "p95_latency", I18N[lang]["p95_latency"], lang)
        plot_grouped_bars(summary, "lat_mean_mean", "lat_mean_ic95",
                          out / "mean_latency", I18N[lang]["mean_latency"], lang)
        plot_grouped_bars(summary, "throughput_mean", "throughput_ic95",
                          out / "throughput", I18N[lang]["throughput"], lang, True)
        plot_grouped_bars(summary, "cpu_mean", "cpu_ic95",
                          out / "mean_cpu_usage", I18N[lang]["cpu"], lang)
        plot_grouped_bars(summary, "memory_mean", "memory_ic95",
                          out / "mean_memory_usage", I18N[lang]["memory"], lang, True)

    summary_csv = Path(root) / "results_summary.csv"
    summary.to_csv(summary_csv, index=False)
    log_info(f"Resumo salvo em {summary_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: generate_report.py <results_directory>")
        sys.exit(1)
    generate(sys.argv[1])
