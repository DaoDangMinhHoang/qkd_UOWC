#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_sim_figs.py — SIMULATION figure set for the BB84-UWOC lab report
═══════════════════════════════════════════════════════════════════════════════

Generates every result figure from the channel model in `uwoc_channel_model.py` —
THE SAME model that was baked into the FPGA ROM. No hardware required.

⚠ EVERY FIGURE PRODUCED HERE IS A MONTE-CARLO SIMULATION RESULT, not a
  measurement on the board. Each figure is labelled "Monte-Carlo simulation" so
  it cannot be mistaken for hardware data.

Unlike generate_report_figures.py, this version samples fading in COHERENCE-TIME
BLOCKS (exactly as uwoc_channel.v does) and counts binomially within each block,
so N ~ 10⁸–10⁹ pulses is feasible → error bars tight enough to put on a slide.

Run:
    python python/report_sim_figs.py
Outputs:
    python/Images/report/*.png  +  sim_results_table.csv
"""

from __future__ import annotations

import csv
import math
import os
import sys

import numpy as np
from scipy.stats import beta as _beta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uwoc_channel_model import (
    WATER_TYPES, OCEAN_TURB_LEVELS, LAMBDA_OPTIONS, LinkConfig, UWOCChannel,
    h2, max_secure_distance, path_loss, e_pol, sigma2_ho_clamped,
    sample_h_s, sample_h_o, n_bar,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ═══════════════════════════════════════════════════════════════════════════
# 1. PLOT STYLE — WHITE background, dark ink, grid pushed to the back
# ═══════════════════════════════════════════════════════════════════════════
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "python", "Images", "report")
os.makedirs(OUT, exist_ok=True)

INK = "#0b0b0b"          # primary ink
INK2 = "#52514e"         # secondary ink
GRID = "#d8d8d4"
SURF = "#ffffff"

plt.rcParams.update({
    "figure.facecolor": SURF,
    "axes.facecolor": SURF,
    "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelcolor": INK,
    "axes.edgecolor": GRID,
    "axes.linewidth": 1.0,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5,
    "legend.fontsize": 10,
    "legend.frameon": True,
    "legend.framealpha": 0.92,
    "legend.edgecolor": GRID,
    "lines.linewidth": 2.0,
    "lines.markersize": 7,
    "figure.dpi": 160,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.12,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "grid.alpha": 0.9,
    "axes.axisbelow": True,
})

# Identity colour palette — first 3 slots of the validated palette (all-pairs CVD-safe)
C_W = {"clear_ocean": "#2a78d6", "coastal": "#eb6834", "harbor": "#1baf7a"}
M_W = {"clear_ocean": "o", "coastal": "s", "harbor": "^"}
WATER_ORDER = ("clear_ocean", "coastal", "harbor")
W_LABEL = {"clear_ocean": "Clear ocean", "coastal": "Coastal",
           "harbor": "Turbid harbor"}

# Turbulence L1–L5 is an ORDERED quantity → monochrome light→dark ramp
C_TURB = ["#bcd7f4", "#7fb1e8", "#4a8ddb", "#2a78d6", "#17497f"]
C_LIMIT = "#b3312c"
QBER_LIMIT = 0.11
LAM_NM = 450

TAG = "Monte-Carlo simulation of the FPGA channel model"


def _save(fig, name, tag=True):
    if tag:
        fig.text(0.995, -0.015, TAG, ha="right", va="top",
                 fontsize=8, color=INK2, style="italic")
    p = os.path.join(OUT, name)
    fig.savefig(p)
    plt.close(fig)
    print(f"   saved  {name}")


def _clopper(k, n):
    """Two-sided 95% confidence interval for the ratio k/n."""
    if n == 0:
        return 0.0, 1.0
    lo = float(_beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(_beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    return lo, hi


# ═══════════════════════════════════════════════════════════════════════════
# 2. MONTE-CARLO OVER COHERENCE-TIME BLOCKS
#    (h is frozen within a block — exactly as uwoc_channel.v, COH_LOG2 = 18)
# ═══════════════════════════════════════════════════════════════════════════
def mc_link(water, d, turb, lam_nm=LAM_NM, target_sift=3000,
            n_min=2_000_000, n_max=2_000_000_000, seed=1, p_z=0.5):
    """
    Simulate the link at (water, d, turb, λ).

    Within each coherence block (50,000 pulses) h_s·h_o is constant; the clicks /
    errors in the block are drawn from a binomial — equivalent to per-qubit
    sampling but feasible at very large N.

    N is chosen automatically to collect enough `target_sift` sifted bits.
    """
    cfg = LinkConfig(lam_nm=lam_nm)
    ch = UWOCChannel(water, float(d), turb, cfg)
    m = ch.mean_metrics()

    q_basis = p_z ** 2 + (1 - p_z) ** 2
    n_need = target_sift / max(m["p_click"] * q_basis, 1e-12)
    N = int(min(max(n_need, n_min), n_max))

    blk = cfg.coherence_pulses                       # 50,000 pulses / block
    n_blk = max(4, int(math.ceil(N / blk)))
    N = n_blk * blk

    rng = np.random.default_rng(seed)
    h = (sample_h_s(ch.sigma2_s, n_blk, rng)
         * sample_h_o(ch.sigma2_ho, n_blk, rng))
    nb = n_bar(h, float(d), water, cfg)

    p_sig = np.clip(1.0 - np.exp(-nb), 0.0, 1.0)     # click from the signal
    Y0 = min(ch.Y0, 1.0)
    p_cl = np.clip(1.0 - (1.0 - Y0) * np.exp(-nb), 0.0, 1.0)

    # --- all pulses: count clicks (to estimate P_click) ---
    n_click = rng.binomial(blk, p_cl).astype(np.int64)

    # --- sifting branch: bases match → sifted ---
    n_att = rng.binomial(blk, q_basis, size=n_blk).astype(np.int64)
    n_sig = rng.binomial(n_att, p_sig)
    n_noise = rng.binomial(n_att - n_sig, Y0)
    n_sift_b = n_sig + n_noise
    n_err_b = (rng.binomial(n_sig, min(ch.e_det, 1.0))
               + rng.binomial(n_noise, 0.5))

    n_sift = int(n_sift_b.sum())
    n_err = int(n_err_b.sum())
    clicks = int(n_click.sum())

    qber = n_err / n_sift if n_sift else float("nan")
    q_lo, q_hi = _clopper(n_err, n_sift)
    pc = clicks / N
    pc_lo, pc_hi = (pc * (1 - 1.96 / math.sqrt(clicks)),
                    pc * (1 + 1.96 / math.sqrt(clicks))) if clicks > 30 else (0.0, 0.0)

    # SKR/pulse: uses the measured QBER; zero once past the security limit
    sift_eff = n_sift / N
    skr_pulse = max(0.0, sift_eff * (1 - 2 * h2(qber))) if n_sift else 0.0
    skr_bps = skr_pulse * cfg.f_rep

    # PER-BLOCK QBER — the quantity channel_monitor.v actually sees
    ok = n_sift_b > 0
    qber_blk = np.where(ok, n_err_b / np.maximum(n_sift_b, 1), np.nan)

    return dict(
        d=float(d), water=water, turb=turb, lam=lam_nm,
        N=N, n_click=clicks, n_sift=n_sift, n_err=n_err,
        p_click=pc, p_click_lo=pc_lo, p_click_hi=pc_hi,
        qber=qber, qber_lo=q_lo, qber_hi=q_hi,
        skr_per_pulse=skr_pulse, skr_bps=skr_bps,
        qber_blk_mean=float(np.nanmean(qber_blk)) if ok.any() else float("nan"),
        qber_blk_std=float(np.nanstd(qber_blk)) if ok.any() else float("nan"),
        outage=float(np.nanmean(qber_blk > QBER_LIMIT)) if ok.any() else 1.0,
        model_qber=m["qber"], model_pclick=m["p_click"],
        secure=bool(n_sift >= 16 and q_hi < QBER_LIMIT),
    )


def model_curve(water, turb, lam_nm, d_lo, d_hi, n=200):
    cfg = LinkConfig(lam_nm=lam_nm)
    dd = np.linspace(max(d_lo, 0.3), d_hi, n)
    pc = np.zeros(n); qb = np.zeros(n); sk = np.zeros(n)
    for i, d in enumerate(dd):
        m = UWOCChannel(water, float(d), turb, cfg).mean_metrics()
        pc[i], qb[i] = m["p_click"], m["qber"]
        sk[i] = max(0.0, 0.5 * m["p_click"] * (1 - 2 * h2(m["qber"])))
    return dd, pc, qb, sk


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Deterministic loss L(d)
# ═══════════════════════════════════════════════════════════════════════════
def fig_pathloss():
    print("[1] path loss L(d)")
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    cfg = LinkConfig(lam_nm=LAM_NM)
    for w in WATER_ORDER:
        g = WATER_TYPES[w].d_grid
        dd = np.linspace(g[0], g[-1], 250)
        L = [path_loss(float(d), w, cfg) for d in dd]
        ax.semilogy(dd, L, "-", color=C_W[w],
                    label=f"{W_LABEL[w]}  (c = {WATER_TYPES[w].c:.3f} m⁻¹)")
        ax.plot([g[-1]], [path_loss(float(g[-1]), w, cfg)],
                M_W[w], color=C_W[w], ms=8,
                markeredgecolor="white", markeredgewidth=1.2)
        ax.annotate(f"{g[-1]:g} m", (g[-1], path_loss(float(g[-1]), w, cfg)),
                    textcoords="offset points", xytext=(6, -3),
                    fontsize=9, color=INK2)
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel("Path loss $L(d)$")
    ax.set_title("Deterministic path loss — geometric spreading × Beer–Lambert")
    ax.legend(loc="upper right")
    ax.set_xlim(0, 84)
    _save(fig, "fig01_pathloss.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 2 — σ²_ho(d) for L1–L5
# ═══════════════════════════════════════════════════════════════════════════
def fig_sigma2_ho():
    print("[2] scintillation index vs distance")
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    dd = np.linspace(1, 60, 60)
    for lv in range(1, 6):
        t = OCEAN_TURB_LEVELS[lv]
        s = [sigma2_ho_clamped(float(d), t["eps"], t["chi_T"], t["w"], LAM_NM)
             for d in dd]
        ax.semilogy(dd, s, "-", color=C_TURB[lv - 1],
                    label=f"L{lv} · {t['name'].title()}")
    ax.axhline(1.0, color=C_LIMIT, ls="--", lw=1.5)
    ax.text(58, 1.15, "weak / strong boundary", ha="right", va="bottom",
            fontsize=9, color=C_LIMIT)
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel(r"Scintillation index  $\sigma^2_{h_o}$")
    ax.set_title("Oceanic turbulence: five calibrated levels (Nikishov spectrum)")
    ax.legend(loc="lower right", ncol=2)
    _save(fig, "fig02_sigma2_ho.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Polarisation error e_pol(d)
# ═══════════════════════════════════════════════════════════════════════════
def fig_epol():
    print("[3] polarization error e_pol(d)")
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    cfg = LinkConfig(lam_nm=LAM_NM)
    for w in WATER_ORDER:
        g = WATER_TYPES[w].d_grid
        dd = np.linspace(0.3, g[-1], 200)
        e = [e_pol(float(d), w, cfg) * 100 for d in dd]
        ax.plot(dd, e, "-", color=C_W[w], label=W_LABEL[w])
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel("Polarization error $e_{pol}$ (%)")
    ax.set_title("Depolarization by multiple scattering — the UWOC-specific\n"
                 "QBER mechanism  ($e_0 = 1\\%$, $k_s = 0.04$, λ = 450 nm)")
    ax.legend(loc="lower right")
    ax.set_xlim(0, 84)
    _save(fig, "fig03_epol.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 4 — QBER vs range (3 water types)
# ═══════════════════════════════════════════════════════════════════════════
def fig_qber_vs_distance(turb=3, store=None):
    print("[4] QBER vs distance")
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    for w in WATER_ORDER:
        g = WATER_TYPES[w].d_grid
        dd, _, qb, _ = model_curve(w, turb, LAM_NM, g[0], g[-1])
        ax.plot(dd, qb * 100, "-", color=C_W[w], lw=1.6, alpha=0.45)

        pts = [mc_link(w, d, turb, seed=11 + i) for i, d in enumerate(g[::2])]
        if store is not None:
            store.extend(pts)
        x = [p["d"] for p in pts if p["n_sift"] >= 16]
        y = np.array([p["qber"] * 100 for p in pts if p["n_sift"] >= 16])
        lo = np.array([p["qber_lo"] * 100 for p in pts if p["n_sift"] >= 16])
        hi = np.array([p["qber_hi"] * 100 for p in pts if p["n_sift"] >= 16])
        ax.errorbar(x, y, yerr=np.vstack([np.maximum(y - lo, 0),
                                          np.maximum(hi - y, 0)]),
                    fmt=M_W[w], color=C_W[w], capsize=3, ms=7, lw=1.4,
                    markeredgecolor="white", markeredgewidth=1.0,
                    label=W_LABEL[w], zorder=3)

    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.6)
    ax.text(0.5, 12, "Shor–Preskill bound  11 %", color=C_LIMIT, fontsize=10)
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel("QBER (%)")
    ax.set_ylim(0, 55)
    ax.set_xlim(0, 84)
    ax.set_title(f"QBER vs distance — turbulence L{turb}, λ = {LAM_NM} nm\n"
                 "markers: simulation with 95 % Clopper–Pearson · lines: model")
    ax.legend(loc="lower right")
    _save(fig, "fig04_qber_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 5 — P_click vs range
# ═══════════════════════════════════════════════════════════════════════════
def fig_pclick_vs_distance(turb=3):
    print("[5] P_click vs distance")
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    Y0 = LinkConfig(lam_nm=LAM_NM).Y0
    for w in WATER_ORDER:
        g = WATER_TYPES[w].d_grid
        dd, pc, _, _ = model_curve(w, turb, LAM_NM, g[0], g[-1])
        ax.semilogy(dd, pc, "-", color=C_W[w], lw=1.6, alpha=0.45)

        pts = [mc_link(w, d, turb, seed=41 + i) for i, d in enumerate(g[::2])]
        x = [p["d"] for p in pts if p["n_click"] > 30]
        y = [p["p_click"] for p in pts if p["n_click"] > 30]
        ax.semilogy(x, y, M_W[w], color=C_W[w], ms=7,
                    markeredgecolor="white", markeredgewidth=1.0,
                    label=W_LABEL[w], zorder=3)

    ax.axhline(Y0, color=INK2, ls=":", lw=1.6)
    ax.text(82, Y0 * 1.25, f"noise floor  $Y_0$ = {Y0:.1e}", ha="right",
            fontsize=9.5, color=INK2)
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel(r"Detection probability  $P_{click}$")
    ax.set_xlim(0, 84)
    ax.set_title(f"Detection probability vs distance — L{turb}, λ = {LAM_NM} nm")
    ax.legend(loc="upper right")
    _save(fig, "fig05_pclick_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 6 — SKR vs range
# ═══════════════════════════════════════════════════════════════════════════
def fig_skr_vs_distance(turb=3):
    print("[6] SKR vs distance")
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    f_rep = LinkConfig().f_rep
    for w in WATER_ORDER:
        g = WATER_TYPES[w].d_grid
        dd, _, _, sk = model_curve(w, turb, LAM_NM, g[0], g[-1])
        y = np.where(sk > 0, sk * f_rep, np.nan)
        ax.semilogy(dd, y, "-", color=C_W[w], lw=1.6, alpha=0.45)

        pts = [mc_link(w, d, turb, seed=71 + i) for i, d in enumerate(g[::2])]
        pos = [p for p in pts if p["skr_bps"] > 0 and p["n_sift"] >= 16]
        if pos:
            ax.semilogy([p["d"] for p in pos], [p["skr_bps"] for p in pos],
                        M_W[w], color=C_W[w], ms=7,
                        markeredgecolor="white", markeredgewidth=1.0,
                        label=W_LABEL[w], zorder=3)
        dead = [p for p in pts if p["skr_bps"] <= 0 or p["n_sift"] < 16]
        if dead:
            ax.semilogy([p["d"] for p in dead], [1.0] * len(dead), "x",
                        color=C_W[w], ms=8, mew=2, zorder=3)
    ax.text(82, 1.35, "×  no secure key", ha="right", fontsize=9.5, color=INK2)
    ax.set_xlabel("Link distance $d$ (m)")
    ax.set_ylabel("Secure key rate (bit/s)")
    ax.set_xlim(0, 84)
    ax.set_ylim(0.6, 3e5)
    ax.set_title(f"Secure key rate vs distance — L{turb}, λ = {LAM_NM} nm,\n"
                 "$f_{rep}$ = 10 MHz, asymptotic BB84")
    ax.legend(loc="upper right")
    _save(fig, "fig06_skr_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 7 — FLAT mean but RISING variance with turbulence level
#            (this is the evidence behind adding qber_jitter)
# ═══════════════════════════════════════════════════════════════════════════
def fig_turbulence_mean_vs_std():
    print("[7] turbulence: mean QBER vs between-window spread")
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.5))
    water, d = "clear_ocean", 20.0
    lv = list(range(1, 6))
    res = [mc_link(water, d, l, target_sift=40_000, seed=200 + l) for l in lv]

    ax = axes[0]
    y = np.array([r["qber"] * 100 for r in res])
    lo = np.array([r["qber_lo"] * 100 for r in res])
    hi = np.array([r["qber_hi"] * 100 for r in res])
    ax.errorbar(lv, y, yerr=np.vstack([y - lo, hi - y]), fmt="o-",
                color=C_W["clear_ocean"], capsize=4, ms=8, lw=2,
                markeredgecolor="white", markeredgewidth=1.2)
    for x_, y_ in zip(lv, y):
        ax.annotate(f"{y_:.2f}%", (x_, y_), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9.5, color=INK2)
    ax.set_ylim(0, max(y) * 2.1)
    ax.set_ylabel("Mean QBER (%)")
    ax.set_title("Mean QBER is nearly flat")

    ax = axes[1]
    s = np.array([r["qber_blk_std"] * 100 for r in res])
    ax.bar(lv, s, width=0.62, color=C_TURB, edgecolor="white", linewidth=1.5)
    for x_, y_ in zip(lv, s):
        ax.annotate(f"{y_:.1f}", (x_, y_), textcoords="offset points",
                    xytext=(0, 5), ha="center", fontsize=9.5, color=INK2)
    ax.set_ylim(0, max(s) * 1.25)
    ax.set_ylabel("Between-window QBER std-dev (%)")
    ax.set_title("Between-window spread rises sharply")

    for ax in axes:
        ax.set_xticks(lv)
        ax.set_xticklabels([f"L{i}\n{OCEAN_TURB_LEVELS[i]['name'].title()}"
                            for i in lv], fontsize=9.5)
        ax.set_xlabel("Oceanic turbulence level")
    fig.suptitle("Turbulence hides in the VARIANCE, not in the mean "
                 f"— clear ocean, d = {d:g} m", fontsize=13.5, fontweight="bold")
    fig.tight_layout()
    _save(fig, "fig07_turbulence_mean_vs_std.png")
    return res


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 8 — Monitoring window size: 2^16 is mandatory
# ═══════════════════════════════════════════════════════════════════════════
def fig_window_size():
    print("[8] monitoring window size")
    water, d, cfg = "clear_ocean", 20.0, LinkConfig(lam_nm=LAM_NM)
    windows = [2 ** k for k in (8, 10, 12, 14, 16, 18)]
    fig, ax = plt.subplots(figsize=(7.8, 4.8))

    for idx, lv in enumerate((1, 5)):
        ch = UWOCChannel(water, d, lv, cfg)
        st = [ch.window_statistics(n_windows=6000, window=w, seed=9 + lv)
              for w in windows]
        y = [s["qber_std"] * 100 for s in st]
        color = C_TURB[0 if lv == 1 else 4]
        ax.semilogx(windows, y, "o-", base=2, color=color, ms=8, lw=2.2,
                    markeredgecolor="white", markeredgewidth=1.2,
                    label=f"L{lv} · {OCEAN_TURB_LEVELS[lv]['name'].title()}")

    ax.axvline(65536, color=C_LIMIT, ls="--", lw=1.6)
    ax.text(65536 * 1.15, ax.get_ylim()[1] * 0.55,
            "deployed window\n$2^{16}$ attempts", color=C_LIMIT, fontsize=10)
    ax.set_xticks(windows)
    ax.set_xticklabels([f"$2^{{{int(math.log2(w))}}}$" for w in windows])
    ax.set_xlabel("Monitoring window size (attempts)")
    ax.set_ylabel("Per-window QBER std-dev (%)")
    ax.set_title("Why the window must be large\n"
                 "small windows measure shot noise, not the channel")
    ax.legend(loc="upper right")
    _save(fig, "fig08_window_size.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 9 — Wavelength comparison (NO twin axis: split into 2 panels)
# ═══════════════════════════════════════════════════════════════════════════
def fig_wavelength(turb=3):
    print("[9] wavelength comparison")
    d_test = {"clear_ocean": 20.0, "coastal": 6.0, "harbor": 1.0}
    lam_hatch = {450: "", 532: "//", 650: "xx"}
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.6))

    x = np.arange(len(WATER_ORDER))
    wbar = 0.26
    all_pc, all_qb = [], []
    handles = []
    for j, lam in enumerate(LAMBDA_OPTIONS):
        pcs, qbs = [], []
        for w in WATER_ORDER:
            m = UWOCChannel(w, d_test[w], turb,
                            LinkConfig(lam_nm=lam)).mean_metrics()
            pcs.append(m["p_click"])
            qbs.append(m["qber"] * 100)
        all_pc += pcs
        all_qb += qbs
        off = (j - 1) * wbar
        b = axes[0].bar(x + off, pcs, wbar * 0.92, color=C_TURB[j + 1],
                        edgecolor="white", linewidth=1.4, hatch=lam_hatch[lam],
                        label=f"λ = {lam} nm")
        handles.append(b)
        axes[1].bar(x + off, qbs, wbar * 0.92, color=C_TURB[j + 1],
                    edgecolor="white", linewidth=1.4, hatch=lam_hatch[lam])
        for xi, v in zip(x + off, pcs):
            axes[0].annotate(f"{v:.1e}", (xi, v), textcoords="offset points",
                             xytext=(0, 5), ha="center", va="bottom",
                             fontsize=8, color=INK2, rotation=90)
        for xi, v in zip(x + off, qbs):
            axes[1].annotate(f"{v:.1f}", (xi, v), textcoords="offset points",
                             xytext=(0, 4), ha="center", fontsize=9, color=INK2)

    axes[0].set_yscale("log")
    axes[0].set_ylim(min(all_pc) * 0.35, max(all_pc) * 60)
    axes[0].set_ylabel(r"$P_{click}$")
    axes[0].set_title("Detection probability  (higher is better)")

    axes[1].axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.6)
    axes[1].set_ylim(0, max(all_qb) * 1.28)
    axes[1].text(2.46, QBER_LIMIT * 100 + 0.6, "Shor–Preskill 11 %",
                 color=C_LIMIT, fontsize=9.5, ha="right", va="bottom")
    axes[1].set_ylabel("QBER (%)")
    axes[1].set_title("Quantum bit error rate  (lower is better)")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([f"{W_LABEL[w]}\n$d$ = {d_test[w]:g} m"
                            for w in WATER_ORDER], fontsize=10)
    fig.suptitle("The optimal wavelength depends on turbidity — "
                 "blue wins in clear ocean, red closes the gap in harbor",
                 fontsize=13, fontweight="bold")
    fig.legend(handles=[h for h in handles], loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, -0.035), frameon=False)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    _save(fig, "fig09_wavelength.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 10 — Maximum secure range (heatmap, outage criterion)
# ═══════════════════════════════════════════════════════════════════════════
def fig_max_secure_distance():
    print("[10] max secure distance heatmap")
    cfg = LinkConfig(lam_nm=LAM_NM)
    lv = list(range(1, 6))
    data = np.zeros((3, 5))
    for i, w in enumerate(WATER_ORDER):
        for j, l in enumerate(lv):
            try:
                data[i, j] = max_secure_distance(w, l, cfg, criterion="outage")
            except Exception:
                data[i, j] = 0.0
        print(f"     {W_LABEL[w]:15s} " +
              " ".join(f"{v:6.2f}" for v in data[i]))

    fig, ax = plt.subplots(figsize=(8.2, 3.5))
    norm = data / data.max(axis=1, keepdims=True).clip(min=1e-9)
    ax.imshow(norm, cmap="Blues", aspect="auto", vmin=0, vmax=1.35)
    for i in range(3):
        for j in range(5):
            ax.text(j, i, f"{data[i, j]:.1f} m", ha="center", va="center",
                    fontsize=13, fontweight="bold",
                    color="white" if norm[i, j] > 0.72 else INK)
    ax.set_xticks(range(5))
    ax.set_xticklabels([f"L{l}\n{OCEAN_TURB_LEVELS[l]['name'].title()}"
                        for l in lv], fontsize=10)
    ax.set_yticks(range(3))
    ax.set_yticklabels([W_LABEL[w] for w in WATER_ORDER], fontsize=11)
    ax.set_xlabel("Oceanic turbulence level")
    ax.grid(False)
    ax.set_title("Maximum secure distance — 10 % outage criterion\n"
                 "λ = 450 nm, μ = 0.1, QBER < 11 %")
    fig.tight_layout()
    _save(fig, "fig10_max_secure_distance.png")
    return data


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 11 — Coherence-time sampling (timing diagram)
# ═══════════════════════════════════════════════════════════════════════════
def fig_coherence_timing():
    print("[11] coherence-time block sampling")
    cfg = LinkConfig(lam_nm=LAM_NM)
    ch = UWOCChannel("clear_ocean", 20.0, 4, cfg)
    rng = np.random.default_rng(7)
    n = 14
    h = sample_h_s(ch.sigma2_s, n, rng) * sample_h_o(ch.sigma2_ho, n, rng)
    t_blk = 2 ** 18 / 50e6 * 1e3           # 5.24 ms

    fig, axes = plt.subplots(2, 1, figsize=(9.4, 5.0),
                             gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    t = np.arange(n + 1) * t_blk
    axes[0].step(t, np.append(h, h[-1]), where="post",
                 color=C_W["clear_ocean"], lw=2.4)
    axes[0].fill_between(t, 0, np.append(h, h[-1]), step="post",
                         color=C_W["clear_ocean"], alpha=0.13)
    axes[0].axhline(1.0, color=INK2, ls=":", lw=1.4)
    axes[0].text(t[-1], 1.04, "E[h] = 1", ha="right", fontsize=9.5, color=INK2)
    axes[0].set_ylabel("Fading  $h = h_s \\cdot h_o$")
    top = max(h.max() * 1.42, 1.8)
    axes[0].set_ylim(0, top)
    y_arrow = top * 0.80
    axes[0].annotate("", xy=(t_blk * 1, y_arrow), xytext=(t_blk * 2, y_arrow),
                     arrowprops=dict(arrowstyle="<->", color=C_LIMIT, lw=1.8))
    axes[0].text(t_blk * 1.5, y_arrow * 1.05,
                 "$2^{18}$ clk = 5.24 ms ≈ $τ_{coh}$",
                 ha="center", va="bottom", fontsize=10.5, color=C_LIMIT)
    axes[0].set_title("Fading is frozen for ~50,000 consecutive pulses\n"
                      "ROM is re-read once per coherence block, not per qubit")

    q = np.linspace(0, t[-1], 900)
    axes[1].vlines(q, 0, 1, color=INK2, lw=0.5, alpha=0.55)
    for k in range(1, n):
        axes[1].axvline(k * t_blk, color=C_LIMIT, lw=1.2, alpha=0.7)
    axes[1].set_yticks([])
    axes[1].set_ylabel("Qubits\n@10 MHz", fontsize=10)
    axes[1].set_xlabel("Time (ms)")
    axes[1].grid(False)
    fig.tight_layout()
    _save(fig, "fig11_coherence_timing.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 12 — Sample size: why confidence intervals must be reported
# ═══════════════════════════════════════════════════════════════════════════
def fig_sample_size():
    print("[12] sample size / confidence interval")
    fig, ax = plt.subplots(figsize=(7.8, 4.8))
    n = np.logspace(1, 4.5, 120)
    ax.loglog(n, 3.0 / n * 100, "-", color=C_W["clear_ocean"], lw=2.4,
              label="95 % upper bound with 0 errors observed  (≈ 3/n)")
    for k, c in ((1, C_W["coastal"]), (3, C_W["harbor"])):
        hi = [_clopper(k, int(nn))[1] * 100 for nn in n if nn > k]
        ax.loglog([nn for nn in n if nn > k], hi, "-", color=c, lw=2.0,
                  label=f"95 % upper bound with {k} error{'s' if k > 1 else ''}")
    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.6)
    ax.text(11, 12.5, "Shor–Preskill 11 %", color=C_LIMIT, fontsize=10)
    ax.axvline(16, color=INK2, ls=":", lw=1.5)
    ax.text(17, 0.09, "MIN_SIFT = 16", fontsize=9.5, color=INK2, rotation=90)
    ax.axvline(1000, color=INK2, ls=":", lw=1.5)
    ax.text(1060, 0.09, "target $n_{sift}$ = 1000", fontsize=9.5, color=INK2,
            rotation=90)
    ax.set_xlabel("Number of sifted bits  $n_{sift}$")
    ax.set_ylabel("95 % upper bound on QBER (%)")
    ax.set_ylim(0.05, 120)
    ax.set_title("Sample size, not channel quality, is the binding constraint\n"
                 "a QBER of 0 % means nothing below ~30 sifted bits")
    ax.legend(loc="upper right", fontsize=9.5)
    _save(fig, "fig12_sample_size.png", tag=False)


# ═══════════════════════════════════════════════════════════════════════════
# CSV TABLE
# ═══════════════════════════════════════════════════════════════════════════
def export_csv(turb=3):
    print("[csv] full results table")
    path = os.path.join(OUT, "sim_results_table.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["water", "distance_m", "turb_level", "lambda_nm",
                     "N_pulses", "n_click", "n_sift", "n_err", "P_click",
                     "QBER_pct", "QBER_lo_pct", "QBER_hi_pct",
                     "SKR_bps", "outage", "secure"])
        rows = []
        for w in WATER_ORDER:
            for i, d in enumerate(WATER_TYPES[w].d_grid):
                r = mc_link(w, d, turb, seed=900 + i)
                rows.append(r)
                wr.writerow([w, d, turb, LAM_NM, r["N"], r["n_click"],
                             r["n_sift"], r["n_err"], f"{r['p_click']:.4e}",
                             f"{r['qber']*100:.2f}", f"{r['qber_lo']*100:.2f}",
                             f"{r['qber_hi']*100:.2f}", f"{r['skr_bps']:.3e}",
                             f"{r['outage']:.3f}",
                             "Yes" if r["secure"] else "No"])
    print(f"   saved  sim_results_table.csv  ({len(rows)} rows)")
    return rows


def main():
    print("=" * 70)
    print("  BB84-UWOC — SIMULATION FIGURES FOR THE LAB REPORT")
    print("  model: Beer-Lambert + Gamma scattering + Lognormal/Weibull")
    print("  mu=0.1  eta_det=0.18  Y0=1.3e-5  f_rep=10 MHz  lambda=450 nm")
    print("=" * 70)
    fig_pathloss()
    fig_sigma2_ho()
    fig_epol()
    fig_qber_vs_distance()
    fig_pclick_vs_distance()
    fig_skr_vs_distance()
    fig_turbulence_mean_vs_std()
    fig_window_size()
    fig_wavelength()
    fig_max_secure_distance()
    fig_coherence_timing()
    fig_sample_size()
    export_csv()
    print("=" * 70)
    print(f"  output -> {OUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
