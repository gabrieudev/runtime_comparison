from pathlib import Path
import sys
import json
import math
from datetime import datetime
import re

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

PNG_DPI = 600
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

# ========================= PARSING DO K6 DE PERFORMANCE =========================

def parse_k6_json(path: Path):
    if not path or not path.exists():
        log_warn(f"k6_summary.json não encontrado: {path}")
        return {}

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as e:
        log_warn(f"Falha ao ler JSON do k6 ({path}): {e}")
        return {}

    metrics = data.get("metrics", {})
    if not metrics:
        log_warn(f"Arquivo k6_summary.json sem seção 'metrics': {path}")
        return {}

    def _get_metric_avg(metric_name):
        m = metrics.get(metric_name)
        if isinstance(m, dict) and "avg" in m:
            return m.get("avg")
        alt = metrics.get(f"{metric_name}{{expected_response:true}}")
        if isinstance(alt, dict) and "avg" in alt:
            return alt.get("avg")
        return None

    def _get_metric_p95(metric_name):
        m = metrics.get(metric_name)
        if isinstance(m, dict) and "p(95)" in m:
            return m.get("p(95)")
        alt = metrics.get(f"{metric_name}{{expected_response:true}}")
        if isinstance(alt, dict) and "p(95)" in alt:
            return alt.get("p(95)")
        return None

    lat_mean = _get_metric_avg("http_req_duration")
    if lat_mean is None:
        lat_mean = _get_metric_avg("http_req_duration{expected_response:true}")
    lat_p95 = _get_metric_p95("http_req_duration")
    if lat_p95 is None:
        lat_p95 = _get_metric_p95("http_req_duration{expected_response:true}")

    http_reqs = None
    http_reqs_m = metrics.get("http_reqs")
    if isinstance(http_reqs_m, dict) and "count" in http_reqs_m:
        http_reqs = int(http_reqs_m.get("count", 0))
    else:
        iters = metrics.get("iterations")
        if isinstance(iters, dict) and "count" in iters:
            http_reqs = int(iters.get("count", 0))

    if lat_mean is None and lat_p95 is None and http_reqs is None:
        log_warn(f"k6_summary.json sem métricas utilizáveis: {path}")
        return {}

    try:
        lat_mean_v = float(lat_mean) if lat_mean is not None else float("nan")
    except Exception:
        lat_mean_v = float("nan")

    try:
        lat_p95_v = float(lat_p95) if lat_p95 is not None else float("nan")
    except Exception:
        lat_p95_v = float("nan")

    try:
        http_reqs_v = int(http_reqs) if http_reqs is not None else 0
    except Exception:
        http_reqs_v = 0

    return {
        "lat_mean": lat_mean_v,
        "lat_p95": lat_p95_v,
        "http_reqs": http_reqs_v,
    }

# ========================= PARSING DO K6 DE SEGURANÇA  =========================

def _sanitize_label(s: str) -> str:
    s = s.strip()
    s = re.sub(r'^\{(.*)\}$', r'\1', s)
    s = re.sub(r'[:=,"]', ' ', s)
    s = re.sub(r'\s+', '_', s)
    s = re.sub(r'[^0-9A-Za-z_]', '_', s)
    return s.strip('_').lower() or "check"

def parse_k6_security(path: Path):
    if not path or not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as e:
        log_warn(f"Falha ao ler k6 security JSON ({path}): {e}")
        return {}

    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict) or not metrics:
        log_warn(f"k6 security JSON sem métricas: {path}")
        return {}

    out = {}
    for mname, mval in metrics.items():
        if not isinstance(mval, dict):
            continue

        if mname == "checks" or mname.startswith("checks"):
            label = "checks"
            if "{" in mname and "}" in mname:
                inner = mname[mname.find("{")+1:mname.find("}")]
                label = _sanitize_label(inner)
            else:
                if "name" in mval and isinstance(mval["name"], str):
                    label = _sanitize_label(mval["name"])
            if "passes" in mval:
                out[f"check_{label}_passes"] = int(mval.get("passes", 0))
            if "fails" in mval:
                out[f"check_{label}_fails"] = int(mval.get("fails", 0))
            if "rate" in mval:
                out[f"check_{label}_rate"] = float(mval.get("rate", 0.0))
            if "count" in mval:
                out[f"check_{label}_count"] = int(mval.get("count", 0))
            if "value" in mval:
                try:
                    out[f"check_{label}_value"] = float(mval.get("value"))
                except Exception:
                    out[f"check_{label}_value"] = str(mval.get("value"))
        else:
            if "check" in mname.lower():
                label = _sanitize_label(mname.replace("checks", "").replace("check", ""))
                if not label:
                    label = _sanitize_label(mname)
                if "passes" in mval:
                    out[f"check_{label}_passes"] = int(mval.get("passes", 0))
                if "fails" in mval:
                    out[f"check_{label}_fails"] = int(mval.get("fails", 0))
                if "rate" in mval:
                    out[f"check_{label}_rate"] = float(mval.get("rate", 0.0))
    return out

# ========================= MONITOR CSV =========================

def parse_monitor_csv(path: Path):
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log_warn(f"Falha ao ler monitor CSV {path}: {e}")
        return {}

    log_info(f"Lendo monitor: {path.name} | colunas={list(df.columns)}")
    out = {}

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

    if "timestamp" in df.columns:
        try:
            out["duration"] = df["timestamp"].max() - df["timestamp"].min()
            log_info(f"Duração monitorada: {out['duration']:.2f}s")
        except Exception:
            log_warn("Erro ao calcular duração")

    return out

# ========================= PARSERS ECOSISTEMA =========================

def parse_github_repo(path: Path):
    try:
        with open(path, "r") as f:
            j = json.load(f)
    except Exception as e:
        log_warn(f"Falha ao ler github JSON {path}: {e}")
        return {}
    out = {}
    out["github_full_name"] = j.get("full_name")
    out["github_stars"] = j.get("stargazers_count")
    out["github_forks"] = j.get("forks_count") or j.get("forks")
    out["github_watchers"] = j.get("subscribers_count") or j.get("watchers_count") or j.get("watchers")
    out["github_open_issues"] = j.get("open_issues_count") or j.get("open_issues")
    out["github_pushed_at"] = j.get("pushed_at")
    out["github_updated_at"] = j.get("updated_at")
    return out

def parse_npm_total(path: Path):
    try:
        txt = path.read_text().strip()
        if txt == "":
            return {}
        try:
            v = int(txt)
            return {"npm_total_packages": v}
        except Exception:
            try:
                j = json.loads(txt)
                if "total_rows" in j:
                    return {"npm_total_packages": int(j.get("total_rows", 0))}
                if "total" in j:
                    return {"npm_total_packages": int(j.get("total", 0))}
            except Exception:
                pass
    except Exception as e:
        log_warn(f"Erro ao ler npm total {path}: {e}")
    return {}

def parse_registry_pkg(path: Path):
    try:
        with open(path, "r") as f:
            j = json.load(f)
    except Exception:
        return {}
    out = {}
    if "time" in j and isinstance(j["time"], dict):
        out["rep_pkg_last_release"] = j["time"].get("modified")
    elif "dist-tags" in j and isinstance(j["dist-tags"], dict) and "latest" in j["dist-tags"]:
        out["rep_pkg_latest_tag"] = j["dist-tags"].get("latest")
    return out

def parse_deno_modules(path: Path):
    out = {}
    try:
        if (path.parent / "deno_total_modules.txt").exists():
            txt = (path.parent / "deno_total_modules.txt").read_text().strip()
            out["deno_total_modules"] = int(txt) if txt.isdigit() else None
        else:
            lines = path.read_text().splitlines()
            out["deno_total_modules"] = len([l for l in lines if l.strip()])
    except Exception as e:
        log_warn(f"Erro ao ler deno modules em {path}: {e}")
    return out

# ========================= COLETA =========================

def collect(root):
    perf_rows = []
    sec_rows = []
    root = Path(root)

    log_info(f"Coletando dados em: {root}")

    for runtime_dir in root.iterdir():
        if not runtime_dir.is_dir():
            continue

        log_info(f"Runtime detectado (perf pass): {runtime_dir.name}")

        for vus_dir in runtime_dir.iterdir():
            if not vus_dir.is_dir():
                continue
            for rep_dir in vus_dir.iterdir():
                if not rep_dir.is_dir():
                    continue

                k6 = parse_k6_json(rep_dir / "k6_summary.json")
                monitor = parse_monitor_csv(rep_dir / "docker_stats.csv") \
                    if (rep_dir / "docker_stats.csv").exists() else {}

                if k6 and "duration" in monitor:
                    duration = monitor.get("duration", None)
                    if duration and duration > 0:
                        perf_rows.append({
                            "runtime": runtime_dir.name,
                            "vus": int(vus_dir.name.replace("vus_", "")),
                            "lat_mean": float(k6.get("lat_mean", float("nan"))),
                            "lat_p95": float(k6.get("lat_p95", float("nan"))),
                            "throughput": float(k6.get("http_reqs", 0)) / float(duration),
                            "cpu": monitor.get("cpu"),
                            "memory": monitor.get("memory"),
                        })
                    else:
                        log_warn(f"Duração inválida no monitor para {rep_dir} (performance ignorada)")
                else:
                    if not k6:
                        log_warn(f"k6 summary ausente ou inválido para performance em {rep_dir}")
                    if "duration" not in monitor:
                        log_warn(f"Monitor ausente/sem duration para {rep_dir} (performance ignorada)")

    for runtime_dir in root.iterdir():
        if not runtime_dir.is_dir():
            continue

        rt_name = runtime_dir.name
        runtime_sec_path = runtime_dir / "k6_security_summary.json"

        if runtime_sec_path.exists():
            log_info(f"Encontrado summary de segurança para runtime {rt_name}: {runtime_sec_path}")
            sec_data = parse_k6_security(runtime_sec_path)

            monitor_info = {}
            monitor_file_a = runtime_dir / "k6_security_monitor.csv"
            if monitor_file_a.exists():
                monitor_info = parse_monitor_csv(monitor_file_a)
                log_info(f"Usando monitor (k6_security_monitor.csv) para {rt_name}")
            else:
                found = False
                for vus_dir in runtime_dir.iterdir():
                    if not vus_dir.is_dir():
                        continue
                    for rep_dir in vus_dir.iterdir():
                        candidate = rep_dir / "docker_stats.csv"
                        if candidate.exists():
                            monitor_info = parse_monitor_csv(candidate)
                            log_info(f"Usando monitor fallback {candidate} para {rt_name}")
                            found = True
                            break
                    if found:
                        break

            sec_row = {
                "runtime": rt_name,
                "vus": 0,
                "rep": "runtime_security",
                "result_path": str(runtime_sec_path),
            }
            if monitor_info:
                sec_row["monitor_duration"] = monitor_info.get("duration")
                sec_row["cpu"] = monitor_info.get("cpu")
                sec_row["memory"] = monitor_info.get("memory")

            sec_row.update(sec_data)
            sec_rows.append(sec_row)
        else:
            log_info(f"Sem summary de segurança para runtime {rt_name} (arquivo esperado: {runtime_sec_path})")

    perf_df = pd.DataFrame(perf_rows)
    sec_df = pd.DataFrame(sec_rows)
    return perf_df, sec_df

# ========================= COLETA ECOSSISTEMA =========================

def collect_ecosystem(root):
    rows = []
    root = Path(root)
    log_info("Coletando dados do ecossistema (por runtime)")

    for runtime_dir in root.iterdir():
        if not runtime_dir.is_dir():
            continue

        eco_dir = runtime_dir / "ecosystem"
        if not eco_dir.exists():
            eco_dir = runtime_dir / "eco_raw"
        if not eco_dir.exists():
            log_info(f"Sem diretório de ecossistema para {runtime_dir.name} (pula)")
            continue

        row = {"runtime": runtime_dir.name}
        gh = {}
        gh_path = eco_dir / "github_repo.json"
        if gh_path.exists():
            gh = parse_github_repo(gh_path)
            row.update(gh)
        else:
            log_info(f"Sem github_repo.json em {eco_dir}")

        npm_path = eco_dir / "npm_total_packages.txt"
        if npm_path.exists():
            npm = parse_npm_total(npm_path)
            row.update(npm)
        else:
            rep_path = eco_dir / "npm_replicate.json"
            if rep_path.exists():
                npm = parse_npm_total(rep_path)
                row.update(npm)

        reg_files = list(eco_dir.glob("registry_*.json"))
        if reg_files:
            reg = parse_registry_pkg(reg_files[0])
            row.update(reg)

        deno_mods = eco_dir / "deno_modules.txt"
        if deno_mods.exists():
            deno = parse_deno_modules(deno_mods)
            row.update(deno)
        else:
            deno_total = eco_dir / "deno_total_modules.txt"
            if deno_total.exists():
                try:
                    v = deno_total.read_text().strip()
                    row["deno_total_modules"] = int(v) if v.isdigit() else None
                except Exception:
                    pass

        rows.append(row)

    if not rows:
        log_info("Nenhum dado de ecossistema coletado")
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    for col in ("github_pushed_at", "github_updated_at", "rep_pkg_last_release"):
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass

    preferred = [
        "runtime",
        "github_full_name",
        "github_stars",
        "github_forks",
        "github_watchers",
        "github_open_issues",
        "github_pushed_at",
        "npm_total_packages",
        "rep_pkg_last_release",
        "deno_total_modules",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols]

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

    perf_df, sec_df = collect(root)

    if perf_df.empty and sec_df.empty:
        log_error("Nenhum dado coletado (performance e segurança vazios). Abortando.")
        return

    if not perf_df.empty:
        log_info(f"Amostras de performance coletadas: {len(perf_df)}")

        summary = summarize(perf_df)
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
    else:
        log_warn("Nenhum dado de performance válido encontrado; pulando geração de gráficos/resumo de performance.")

    # ========================= salvar CSV de segurança =========================
    if not sec_df.empty:
        cols = list(sec_df.columns)
        preferred = ["runtime", "vus", "rep", "result_path", "monitor_duration", "cpu", "memory"]
        others = [c for c in cols if c not in preferred]
        ordered = [c for c in preferred if c in cols] + sorted(others)
        sec_df = sec_df[ordered]
        security_csv = Path(root) / "security_results.csv"
        sec_df.to_csv(security_csv, index=False)
        log_info(f"Resultados de segurança salvos em {security_csv} ({len(sec_df)} linhas)")
    else:
        log_info("Nenhum resultado de segurança encontrado; pulando CSV de segurança.")

    # ========================= salvar CSV do ECOSSISTEMA =========================
    eco_df = collect_ecosystem(root)
    if not eco_df.empty:
        eco_csv = Path(root) / "ecosystem_results.csv"
        eco_df.to_csv(eco_csv, index=False)
        log_info(f"Resultados do ecossistema salvos em {eco_csv} ({len(eco_df)} runtimes)")
    else:
        log_info("Nenhum dado de ecossistema encontrado; pulando CSV do ecossistema.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: generate_report.py <results_directory>")
        sys.exit(1)
    generate(sys.argv[1])
