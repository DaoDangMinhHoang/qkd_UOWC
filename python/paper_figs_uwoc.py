#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_figs_uwoc.py — Build the paper figures from real FPGA data (UWOC channel)
═══════════════════════════════════════════════════════════════════════════════

Reads  data/fpga_points.csv  and  data/clicks_<tag>.csv   (produced by fpga_collect.py)
Writes Images/fig_uwoc_*.png  +  Images/table_uwoc_results.csv/.tex

PRESENTATION RULES — deliberately different from the atmospheric paper's script:
  [1] EVERY QBER point carries a two-sided Clopper-Pearson interval. Underwater
      P_click ~ 10⁻²…10⁻⁴, so each point holds only a few hundred sifted bits; drawing
      the bare point value would lie about how certain the measurement is.
  [2] Points with n_sift < MIN_SIFT are NOT drawn as measurements but as UPPER-BOUND arrows.
      A point of 0 errors / 3 sifted bits is not "QBER = 0%".
  [3] Any figure holding FPGA data also carries the model curve on the same axes — the
      paper has to show the hardware emulator reproduces the physics correctly, not
      merely that it runs.

Run:
    python python/paper_figs_uwoc.py
"""

from __future__ import annotations

import csv
import glob
import os
import sys

import numpy as np
from scipy.stats import beta as _beta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                             # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uwoc_channel_model import (                            # noqa: E402
    WATER_TYPES, LinkConfig, UWOCChannel, h2,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "Images")

MIN_SIFT = 16
QBER_LIMIT = 0.11
CONF = 0.95

# ---- IEEE style, matching regen_paper_figs.py so both papers stay consistent ----
FIGW, FIGW2 = 3.5, 7.16
plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.labelsize": 11,
    "legend.fontsize": 8, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "lines.linewidth": 1.5, "lines.markersize": 5,
    "figure.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.05,
})

C_FPGA = "#d62728"
C_MODEL = "#1f77b4"
C_LIMIT = "#555555"
C_W = {"clear_ocean": "#1f77b4", "coastal": "#2ca02c", "harbor": "#d62728"}


# ═══════════════════════════════════════════════════════════════════════════
def cp_interval(k: int, n: int, conf: float = CONF):
    """Two-sided Clopper-Pearson interval for k errors out of n trials."""
    if n <= 0:
        return 0.0, 1.0
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else float(_beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k >= n else float(_beta.ppf(1 - a, k + 1, n - k))
    return lo, hi


def load_points():
    p = os.path.join(DATA, "fpga_points.csv")
    if not os.path.exists(p):
        sys.exit("Chưa có %s — chạy fpga_collect.py trước." % p)
    rows = []
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k in ("distance_m", "p_click", "sift_eff", "qber", "qber_hi",
                      "skr_per_pulse", "seconds", "rate_qps", "p_click_model",
                      "qber_model"):
                r[k] = float(r[k])
            for k in ("dist_idx", "turb", "lam_nm", "n_qubit", "n_click",
                      "n_sift", "n_err"):
                r[k] = int(r[k])
            r["secure"] = r["secure"] == "True"
            r["qber_lo"], r["qber_hi2"] = cp_interval(r["n_err"], r["n_sift"])
            r["valid"] = r["n_sift"] >= MIN_SIFT
            rows.append(r)
    return rows


def pick(rows, prefix, phase="fixed"):
    sel = [r for r in rows if r["phase"] == phase
           and r["tag"].startswith("%s_%s" % (phase, prefix))]
    return sorted(sel, key=lambda r: (r["water"], r["dist_idx"], r["turb"],
                                      r["lam_nm"]))


def model_curve(water, turb, lam_nm, dmax, n=120):
    cfg = LinkConfig(lam_nm=lam_nm)
    dd = np.linspace(0.5, dmax, n)
    pc, qb, sk = [], [], []
    for d in dd:
        m = UWOCChannel(water, float(d), turb, cfg).mean_metrics()
        pc.append(m["p_click"])
        qb.append(m["qber"])
        sk.append(0.5 * m["p_click"] * max(0.0, 1 - 2 * h2(m["qber"])))
    return dd, np.array(pc), np.array(qb), np.array(sk)


def qber_errorbars(rows):
    """Return (x_ok, q_ok, yerr_ok), (x_lim, hi_lim) — measured points and upper-bound-only points."""
    ok = [r for r in rows if r["valid"]]
    lim = [r for r in rows if not r["valid"]]
    xo = np.array([r["distance_m"] for r in ok])
    qo = np.array([r["qber"] for r in ok]) * 100
    lo = qo - np.array([r["qber_lo"] for r in ok]) * 100
    hi = np.array([r["qber_hi2"] for r in ok]) * 100 - qo
    xl = np.array([r["distance_m"] for r in lim])
    hl = np.array([r["qber_hi2"] for r in lim]) * 100
    return (xo, qo, np.vstack([lo, hi])), (xl, hl)


def _save(fig, name):
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, name))
    plt.close(fig)
    print("  ✓", name)


# ═══════════════════════════════════════════════════════════════════════════
# FIG 1 — P_click vs range: FPGA against the model  (emulator validation)
# ═══════════════════════════════════════════════════════════════════════════
def fig_pclick(rows):
    A = pick(rows, "A_dist")
    if not A:
        return
    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    dd, pc, _, _ = model_curve("clear_ocean", 5, 450,
                               max(r["distance_m"] for r in A) * 1.1)
    ax.semilogy(dd, pc, "-", color=C_MODEL, label="Analytical model")

    x = [r["distance_m"] for r in A]
    y = [r["p_click"] for r in A]
    # Poisson error bars on the click count itself
    ye = [r["p_click"] / np.sqrt(max(r["n_click"], 1)) for r in A]
    ax.errorbar(x, y, yerr=ye, fmt="o", color=C_FPGA, capsize=2,
                label="FPGA measurement", zorder=3)

    ax.set_xlabel("Link distance, $d$ (m)")
    ax.set_ylabel(r"Detection probability $P_{\rm click}$")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(framealpha=0.0)
    _save(fig, "fig_uwoc_pclick_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 2 — QBER vs range (the headline figure)
# ═══════════════════════════════════════════════════════════════════════════
def fig_qber_distance(rows):
    A = pick(rows, "A_dist")
    if not A:
        return
    fig, ax = plt.subplots(figsize=(FIGW, 2.9))
    dmax = max(r["distance_m"] for r in A) * 1.1
    dd, _, qb, _ = model_curve("clear_ocean", 5, 450, dmax)
    ax.plot(dd, qb * 100, "-", color=C_MODEL, label="Analytical model")

    (xo, qo, ye), (xl, hl) = qber_errorbars(A)
    if len(xo):
        ax.errorbar(xo, qo, yerr=ye, fmt="o", color=C_FPGA, capsize=2,
                    label="FPGA (95% Clopper–Pearson)", zorder=3)
    if len(xl):
        # uplims=True: the convention for "this is an UPPER BOUND"; matplotlib draws a
        # downward arrow. It must not be drawn as a measurement — 0 errors / 3 sifted
        # bits is not a QBER measurement.
        ax.errorbar(xl, hl, yerr=hl * 0.30, uplims=True, fmt="_",
                    color=C_FPGA, capsize=2, lw=1.0,
                    label=r"FPGA upper bound ($n_{\rm sift}<%d$)" % MIN_SIFT,
                    zorder=3)

    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.2,
               label="Shor–Preskill bound (11%)")
    ax.set_xlabel("Link distance, $d$ (m)")
    ax.set_ylabel("QBER (%)")
    top = 60.0
    if len(xl):
        top = max(top, float(hl.max()) * 1.15)
    if len(xo):
        top = max(top, float((qo + ye[1]).max()) * 1.15)
    ax.set_ylim(0, min(top, 105))
    ax.grid(True, alpha=0.3)
    ax.legend(framealpha=0.0, loc="upper left")
    _save(fig, "fig_uwoc_qber_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 3 — SKR vs range
# ═══════════════════════════════════════════════════════════════════════════
def fig_skr(rows):
    A = pick(rows, "A_dist")
    if not A:
        return
    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    dd, _, _, sk = model_curve("clear_ocean", 5, 450,
                               max(r["distance_m"] for r in A) * 1.1)
    sk = np.where(sk > 0, sk, np.nan)
    ax.semilogy(dd, sk, "-", color=C_MODEL, label="Analytical model")

    pos = [r for r in A if r["skr_per_pulse"] > 0]
    zero = [r for r in A if r["skr_per_pulse"] <= 0]
    if pos:
        ax.semilogy([r["distance_m"] for r in pos],
                    [r["skr_per_pulse"] for r in pos], "o", color=C_FPGA,
                    label="FPGA measurement")
    for r in zero:
        ax.annotate("no key", (r["distance_m"], ax.get_ylim()[0] * 3),
                    ha="center", fontsize=7, color=C_LIMIT, rotation=90)
    ax.set_xlabel("Link distance, $d$ (m)")
    ax.set_ylabel("Secure key rate (bits/pulse)")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(framealpha=0.0)
    _save(fig, "fig_uwoc_skr_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 4 — QBER vs turbulence level (expectation: almost flat)
# ═══════════════════════════════════════════════════════════════════════════
def fig_turbulence(rows):
    B = sorted(pick(rows, "B_turb"), key=lambda r: r["turb"])
    if not B:
        return
    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    x = np.array([r["turb"] for r in B])

    qm = []
    for r in B:
        qm.append(UWOCChannel("clear_ocean", r["distance_m"], r["turb"],
                              LinkConfig(lam_nm=r["lam_nm"])
                              ).mean_metrics()["qber"] * 100)
    ax.plot(x, qm, "-s", color=C_MODEL, mfc="none", label="Analytical model")

    ok = [r for r in B if r["valid"]]
    if ok:
        xo = np.array([r["turb"] for r in ok])
        qo = np.array([r["qber"] for r in ok]) * 100
        lo = qo - np.array([r["qber_lo"] for r in ok]) * 100
        hi = np.array([r["qber_hi2"] for r in ok]) * 100 - qo
        ax.errorbar(xo, qo, yerr=np.vstack([lo, hi]), fmt="o", color=C_FPGA,
                    capsize=2, label="FPGA (95% CP)", zorder=3)

    ax.set_xlabel("Oceanic turbulence level")
    ax.set_ylabel("QBER (%)")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["L1\nvery weak", "L2\nweak", "L3\nmod.",
                        "L4\nstrong", "L5\nsevere"], fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(framealpha=0.0)
    _save(fig, "fig_uwoc_qber_vs_turbulence.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 5 — The optimal λ depends on the water type (lam ↔ red)
# ═══════════════════════════════════════════════════════════════════════════
def fig_wavelength(rows):
    C = pick(rows, "C_lam")
    if not C:
        return
    groups = {}
    for r in C:
        groups.setdefault(r["water"], []).append(r)
    if not groups:
        return

    fig, axes = plt.subplots(1, len(groups), figsize=(FIGW2, 2.6), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, (water, rs) in zip(axes, sorted(groups.items())):
        rs = sorted(rs, key=lambda r: r["lam_nm"])
        lams = [r["lam_nm"] for r in rs]
        xi = np.arange(len(lams))
        meas = [r["p_click"] for r in rs]
        mod = [r["p_click_model"] for r in rs]
        err = [r["p_click"] / np.sqrt(max(r["n_click"], 1)) for r in rs]

        ax.bar(xi - 0.2, meas, 0.4, yerr=err, capsize=2, color=C_FPGA,
               edgecolor="k", lw=0.4, label="FPGA")
        ax.bar(xi + 0.2, mod, 0.4, color=C_MODEL, edgecolor="k", lw=0.4,
               label="Model")
        ax.set_xticks(xi)
        ax.set_xticklabels(["%d nm" % l for l in lams])
        ax.set_title("%s, $d$ = %g m" % (WATER_TYPES[water].name,
                                         rs[0]["distance_m"]), fontsize=9)
        ax.set_ylabel(r"$P_{\rm click}$")
        ax.grid(True, alpha=0.3, axis="y")
        ax.legend(framealpha=0.0, fontsize=7)
    _save(fig, "fig_uwoc_wavelength.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 6 — The three water types
# ═══════════════════════════════════════════════════════════════════════════
def fig_water_types(rows):
    pts = pick(rows, "A_dist") + pick(rows, "D_")
    if not pts:
        return
    groups = {}
    for r in pts:
        groups.setdefault(r["water"], []).append(r)

    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    for water, rs in sorted(groups.items()):
        rs = sorted(rs, key=lambda r: r["distance_m"])
        c = C_W.get(water, "k")
        dmax = max(r["distance_m"] for r in rs) * 1.15
        dd, pc, _, _ = model_curve(water, rs[0]["turb"], rs[0]["lam_nm"], dmax)
        ax.semilogy(dd, pc, "-", color=c, lw=1.2, alpha=0.7)
        ax.semilogy([r["distance_m"] for r in rs], [r["p_click"] for r in rs],
                    "o", color=c, label=WATER_TYPES[water].name)
    ax.set_xlabel("Link distance, $d$ (m)")
    ax.set_ylabel(r"$P_{\rm click}$")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(framealpha=0.0, title="Markers: FPGA · Lines: model",
              title_fontsize=7)
    _save(fig, "fig_uwoc_water_types.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 7 — METHODOLOGY figure: why N = 5,000–10,000 qubits is not enough
# ═══════════════════════════════════════════════════════════════════════════
def fig_sample_size(rows):
    """Achievable QBER upper bound versus transmitted qubits, for several ranges.

    This figure answers the question 'why did the measured QBER come out 0%'
    directly. With 0 errors over n sifted bits the 95% upper bound is 1−0.05^(1/n)
    ≈ 3/n. Asserting QBER < 11% needs n_sift ≳ 27; MEASURING QBER ~1.6% needs n_sift ~10³.
    """
    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    N = np.logspace(3, 6.3, 200)
    for d, p in ((5.0, 1.039e-2), (15.0, 3.511e-3), (25.0, 1.18e-3)):
        nsift = N * p * 0.5
        hi = np.array([cp_interval(0, max(int(n), 1))[1] for n in nsift]) * 100
        ax.loglog(N, hi, label="$d$ = %g m" % d)

    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.2,
               label="11% bound")
    ax.axvspan(5e3, 1e4, color="#999", alpha=0.25)
    ax.annotate("$N$ of the\natmospheric study", xy=(7e3, 0.35),
                xytext=(2.2e4, 0.16), fontsize=6.5, color="#444",
                arrowprops=dict(arrowstyle="->", color="#444", lw=0.7))
    ax.set_xlabel("Transmitted pulses, $N$")
    ax.set_ylabel("QBER upper bound (%)")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(framealpha=0.0, fontsize=7)
    _save(fig, "fig_uwoc_sample_size.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIG 8 — QBER versus the SNR proxy (irrad), from the per-click data
# ═══════════════════════════════════════════════════════════════════════════
def fig_qber_vs_irradiance():
    recs = []
    for p in glob.glob(os.path.join(DATA, "clicks_*.csv")):
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if int(r["bmatch"]):
                    recs.append((int(r["irrad"]), int(r["err"])))
    if len(recs) < 200:
        print("  (bỏ qua fig_uwoc_qber_vs_snr: mới %d bit sàng)" % len(recs))
        return
    irr = np.array([a for a, _ in recs])
    err = np.array([b for _, b in recs])

    edges = np.quantile(irr, np.linspace(0, 1, 7))
    edges = np.unique(edges)
    xs, qs, los, his = [], [], [], []
    for i in range(len(edges) - 1):
        # ⚠ the parentheses are mandatory: Python reads `a & b if c else d` as
        #   `(a & b) if c else d`, which loses the lower bound in the else branch.
        upper = ((irr <= edges[i + 1]) if i == len(edges) - 2
                 else (irr < edges[i + 1]))
        m = (irr >= edges[i]) & upper
        n = int(m.sum())
        if n < 20:
            continue
        k = int(err[m].sum())
        lo, hi = cp_interval(k, n)
        xs.append(float(irr[m].mean()))
        qs.append(k / n * 100)
        los.append(qs[-1] - lo * 100)
        his.append(hi * 100 - qs[-1])
    if not xs:
        return

    fig, ax = plt.subplots(figsize=(FIGW, 2.7))
    ax.errorbar(xs, qs, yerr=np.vstack([los, his]), fmt="o-", color=C_FPGA,
                capsize=2, label="FPGA, all configurations pooled")
    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.2,
               label="11% bound")
    ax.set_xlabel("Received irradiance proxy (8-bit)")
    ax.set_ylabel("QBER (%)")
    ax.grid(True, alpha=0.3)
    ax.legend(framealpha=0.0, fontsize=7)
    _save(fig, "fig_uwoc_qber_vs_snr.png")


# ═══════════════════════════════════════════════════════════════════════════
def write_table(rows):
    cols = [("water", "Water"), ("distance_m", "d (m)"), ("turb", "L"),
            ("lam_nm", "lambda (nm)"), ("n_qubit", "N"), ("n_click", "clicks"),
            ("n_sift", "n_sift"), ("n_err", "errors"),
            ("p_click", "P_click"), ("p_click_model", "P_click (model)"),
            ("qber", "QBER"), ("qber_hi2", "QBER upper 95%"),
            ("qber_model", "QBER (model)"), ("skr_per_pulse", "SKR/pulse")]
    p = os.path.join(OUT, "table_uwoc_results.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([h for _, h in cols])
        for r in rows:
            w.writerow([r[k] for k, _ in cols])
    print("  ✓ table_uwoc_results.csv")

    p = os.path.join(OUT, "table_uwoc_results.tex")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\\begin{tabular}{l r c c r r r r r r}\n\\hline\n")
        f.write("Water & $d$ (m) & $L$ & $\\lambda$ & $N$ & clicks & "
                "$n_{\\rm sift}$ & QBER & 95\\% u.b. & model \\\\\n\\hline\n")
        for r in rows:
            f.write("%s & %g & %d & %d & %d & %d & %d & %.2f\\%% & %.2f\\%% & "
                    "%.2f\\%% \\\\\n" % (
                        WATER_TYPES[r["water"]].name, r["distance_m"],
                        r["turb"], r["lam_nm"], r["n_qubit"], r["n_click"],
                        r["n_sift"], r["qber"] * 100, r["qber_hi2"] * 100,
                        r["qber_model"] * 100))
        f.write("\\hline\n\\end{tabular}\n")
    print("  ✓ table_uwoc_results.tex")


def summarise(rows):
    print("\n  ĐỐI CHIẾU FPGA ↔ MÔ HÌNH")
    tot_m = sum(r["p_click_model"] * r["n_qubit"] for r in rows)
    tot_c = sum(r["n_click"] for r in rows)
    print("    click đo được / click mô hình dự đoán = %d / %.0f = %.3f"
          % (tot_c, tot_m, tot_c / max(tot_m, 1e-9)))
    ok = [r for r in rows if r["valid"]]
    if ok:
        ns = sum(r["n_sift"] for r in ok)
        ne = sum(r["n_err"] for r in ok)
        lo, hi = cp_interval(ne, ns)
        print("    QBER gộp trên %d bit sàng = %.2f%%  [%.2f%%, %.2f%%]"
              % (ns, ne / ns * 100, lo * 100, hi * 100))
    print("    tổng thời gian đo = %.2f giờ, %d cấu hình"
          % (sum(r["seconds"] for r in rows) / 3600, len(rows)))


def main():
    global DATA, OUT
    import argparse
    ap = argparse.ArgumentParser(description="Dựng hình bài báo UWOC")
    ap.add_argument("--data", default=DATA, help="thư mục số liệu FPGA")
    ap.add_argument("--out", default=OUT, help="thư mục hình ra")
    a = ap.parse_args()

    DATA, OUT = os.path.abspath(a.data), os.path.abspath(a.out)
    os.makedirs(OUT, exist_ok=True)

    rows = load_points()
    print("Đã nạp %d điểm đo từ %s\n" % (len(rows), DATA))
    fig_pclick(rows)
    fig_qber_distance(rows)
    fig_skr(rows)
    fig_turbulence(rows)
    fig_wavelength(rows)
    fig_water_types(rows)
    fig_sample_size(rows)
    fig_qber_vs_irradiance()
    write_table(rows)
    summarise(rows)
    print("\nHình ở %s" % OUT)


if __name__ == "__main__":
    main()
