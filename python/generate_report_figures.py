#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_report_figures.py — Builds the BB84-UWOC simulation figures for the report
═══════════════════════════════════════════════════════════════════════════════

Uses THE SAME existing UWOC channel model (uwoc_channel_model.py) to run a
qubit-level Monte-Carlo and plot the results. NO FPGA hardware required.

Writes into  python/Images/sim_report/  :
  1. QBER vs range (3 water types)
  2. P_click vs range (3 water types)
  3. SKR vs range (3 water types)
  4. QBER vs turbulence level (5 levels)
  5. Wavelength comparison (λ = 450, 532, 650 nm)
  6. Summary table of maximum secure range

Run:
    python python/generate_report_figures.py
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
from scipy.stats import beta as _beta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uwoc_channel_model import (
    WATER_TYPES, OCEAN_TURB_LEVELS, LAMBDA_OPTIONS, LinkConfig,
    UWOCChannel, h2, max_secure_distance, path_loss, e_pol,
    p_click as p_click_fn, qber_from_nbar, n_bar,
)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.ticker as mticker

# ═══════════════════════════════════════════════════════════════════════════
# PLOT CONFIGURATION — IEEE / scientific-report style
# ═══════════════════════════════════════════════════════════════════════════
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "python", "Images", "sim_report")
os.makedirs(OUT, exist_ok=True)

FIGW = 7.0        # single-figure width (inch)
FIGH = 4.5        # height
FIGW2 = 10.0      # double / triple column figure

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "lines.linewidth": 2.0,
    "lines.markersize": 6,
    "figure.dpi": 200,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.08,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

# Colour palette
C_WATER = {
    "clear_ocean": "#1976D2",   # dark blue
    "coastal":     "#2E7D32",   # dark green
    "harbor":      "#D32F2F",   # dark red
}
C_LAM = {450: "#1565C0", 532: "#2E7D32", 650: "#C62828"}
C_TURB = ["#E3F2FD", "#42A5F5", "#1976D2", "#0D47A1", "#1A237E"]
C_LIMIT = "#757575"
QBER_LIMIT = 0.11

WATER_ORDER = ("clear_ocean", "coastal", "harbor")
WATER_LABELS = {"clear_ocean": "Clear Ocean", "coastal": "Coastal",
                "harbor": "Harbor (Turbid)"}


def _save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {name}")


# ═══════════════════════════════════════════════════════════════════════════
# MODEL COMPUTATION — solid lines (analytical mean)
# ═══════════════════════════════════════════════════════════════════════════
def analytical_curve(water, turb, lam_nm, d_range, n=150):
    """Compute P_click, QBER and SKR versus range from the analytical formulas."""
    cfg = LinkConfig(lam_nm=lam_nm)
    dd = np.linspace(max(d_range[0], 0.5), d_range[1], n)
    pc, qb, sk = np.zeros(n), np.zeros(n), np.zeros(n)
    for i, d in enumerate(dd):
        m = UWOCChannel(water, float(d), turb, cfg).mean_metrics()
        pc[i] = m["p_click"]
        qb[i] = m["qber"]
        sk[i] = max(0.0, 0.5 * m["p_click"] * (1 - 2 * h2(m["qber"])))
    return dd, pc, qb, sk


def mc_points(water, turb, lam_nm, distances, n_qubit=100_000, seed=42):
    """Run a qubit-level Monte-Carlo at each range and return the statistics."""
    cfg = LinkConfig(lam_nm=lam_nm)
    results = []
    for i, d in enumerate(distances):
        ch = UWOCChannel(water, float(d), turb, cfg)
        r = ch.simulate(n_qubit, seed=seed + i * 7)
        # Clopper–Pearson interval cho QBER
        n_sift = int(r["sifted"].sum())
        n_err  = int((r["sifted"] & r["error"]).sum())
        q = n_err / n_sift if n_sift > 0 else 0.5
        q_lo = float(_beta.ppf(0.025, max(n_err, 1), n_sift - n_err + 1)) if n_sift > 0 else 0.0
        q_hi = float(_beta.ppf(0.975, n_err + 1, max(n_sift - n_err, 1))) if n_sift > 0 else 1.0
        results.append(dict(
            d=d, p_click=r["p_click"], qber=q, qber_lo=q_lo, qber_hi=q_hi,
            n_sift=n_sift, n_err=n_err, n_click=int(r["click"].sum()),
            skr_per_pulse=r["skr_per_pulse"],
            secure=(n_sift >= 16) and (q_hi < QBER_LIMIT),
        ))
    return results


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 1 — QBER vs range (3 water types)
# ═══════════════════════════════════════════════════════════════════════════
def fig1_qber_vs_distance():
    print("\n[Fig 1] QBER vs Distance — 3 water types")
    fig, ax = plt.subplots(figsize=(FIGW, FIGH))

    turb = 3  # moderate
    for water in WATER_ORDER:
        grid = WATER_TYPES[water].d_grid
        d_max = grid[-1]
        dd, _, qb, _ = analytical_curve(water, turb, 450, (grid[0], d_max))

        # Analytical curve
        ax.plot(dd, qb * 100, "-", color=C_WATER[water], lw=2.0, alpha=0.4)

        # Monte-Carlo points
        mc_dists = list(grid[::2])  # take every 2nd point
        pts = mc_points(water, turb, 450, mc_dists, n_qubit=80_000)
        x = [p["d"] for p in pts if p["n_sift"] >= 16]
        y = [p["qber"] * 100 for p in pts if p["n_sift"] >= 16]
        y_lo = [p["qber_lo"] * 100 for p in pts if p["n_sift"] >= 16]
        y_hi = [p["qber_hi"] * 100 for p in pts if p["n_sift"] >= 16]
        if x:
            y_arr = np.array(y)
            yerr = np.vstack([
                np.maximum(y_arr - np.array(y_lo), 0),
                np.maximum(np.array(y_hi) - y_arr, 0),
            ])
            ax.errorbar(x, y, yerr=yerr, fmt="o", color=C_WATER[water],
                        capsize=3, markersize=5, label=WATER_LABELS[water],
                        zorder=3)

    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.5,
               label="Shor–Preskill bound (11%)")
    ax.set_xlabel("Link Distance $d$ (m)")
    ax.set_ylabel("QBER (%)")
    ax.set_ylim(0, 55)
    ax.set_title("QBER vs Distance — BB84 over UWOC (Turbulence L3, λ = 450 nm)")
    ax.legend(loc="upper left", framealpha=0.85)
    _save(fig, "fig1_qber_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 2 — P_click vs range (3 water types, log axis)
# ═══════════════════════════════════════════════════════════════════════════
def fig2_pclick_vs_distance():
    print("[Fig 2] P_click vs Distance — 3 water types")
    fig, ax = plt.subplots(figsize=(FIGW, FIGH))

    turb = 3
    for water in WATER_ORDER:
        grid = WATER_TYPES[water].d_grid
        dd, pc, _, _ = analytical_curve(water, turb, 450, (grid[0], grid[-1]))
        ax.semilogy(dd, pc, "-", color=C_WATER[water], lw=2.0, alpha=0.4)

        mc_dists = list(grid[::2])
        pts = mc_points(water, turb, 450, mc_dists, n_qubit=80_000, seed=100)
        x = [p["d"] for p in pts]
        y = [p["p_click"] for p in pts]
        # Poisson error bars
        ye = [p["p_click"] / max(np.sqrt(p["n_click"]), 1) for p in pts]
        ax.errorbar(x, y, yerr=ye, fmt="s", color=C_WATER[water],
                    capsize=3, markersize=5, label=WATER_LABELS[water],
                    zorder=3)

    ax.set_xlabel("Link Distance $d$ (m)")
    ax.set_ylabel(r"Detection Probability $P_{\rm click}$")
    ax.set_title(r"$P_{\rm click}$ vs Distance — BB84 over UWOC (L3, λ = 450 nm)")
    ax.legend(loc="lower left", framealpha=0.85)
    _save(fig, "fig2_pclick_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 3 — SKR vs range (3 water types)
# ═══════════════════════════════════════════════════════════════════════════
def fig3_skr_vs_distance():
    print("[Fig 3] SKR vs Distance — 3 water types")
    fig, ax = plt.subplots(figsize=(FIGW, FIGH))

    turb = 3
    for water in WATER_ORDER:
        grid = WATER_TYPES[water].d_grid
        dd, _, _, sk = analytical_curve(water, turb, 450, (grid[0], grid[-1]))
        sk_plot = np.where(sk > 0, sk, np.nan)
        ax.semilogy(dd, sk_plot, "-", color=C_WATER[water], lw=2.0, alpha=0.4)

        mc_dists = list(grid[::2])
        pts = mc_points(water, turb, 450, mc_dists, n_qubit=80_000, seed=200)
        pos = [p for p in pts if p["skr_per_pulse"] > 0]
        if pos:
            ax.semilogy([p["d"] for p in pos],
                        [p["skr_per_pulse"] for p in pos],
                        "^", color=C_WATER[water], markersize=6,
                        label=WATER_LABELS[water], zorder=3)
        # Mark the points where no key can be generated
        zero = [p for p in pts if p["skr_per_pulse"] <= 0]
        for p in zero:
            ax.annotate("X", (p["d"], ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 1e-8),
                        ha="center", fontsize=9, color=C_WATER[water])

    ax.set_xlabel("Link Distance $d$ (m)")
    ax.set_ylabel("Secure Key Rate (bits/pulse)")
    ax.set_title("SKR vs Distance — BB84 over UWOC (L3, λ = 450 nm)")
    ax.legend(loc="upper right", framealpha=0.85)
    _save(fig, "fig3_skr_vs_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 4 — QBER vs turbulence level (clear ocean, 3 ranges)
# ═══════════════════════════════════════════════════════════════════════════
def fig4_qber_vs_turbulence():
    print("[Fig 4] QBER vs Turbulence Level")
    fig, ax = plt.subplots(figsize=(FIGW, FIGH))

    water = "clear_ocean"
    test_dists = [10, 25, 45]
    markers = ["o", "s", "D"]
    colors = ["#1565C0", "#F57F17", "#C62828"]

    for d, mk, clr in zip(test_dists, markers, colors):
        # Analytical
        levels = list(range(1, 6))
        qm = []
        for lv in levels:
            m = UWOCChannel(water, float(d), lv, LinkConfig(lam_nm=450)).mean_metrics()
            qm.append(m["qber"] * 100)
        ax.plot(levels, qm, "-", color=clr, lw=1.5, alpha=0.4)

        # Monte-Carlo
        q_mc = []
        q_lo_mc, q_hi_mc = [], []
        for lv in levels:
            ch = UWOCChannel(water, float(d), lv, LinkConfig(lam_nm=450))
            r = ch.simulate(80_000, seed=300 + lv + d)
            n_sift = int(r["sifted"].sum())
            n_err = int((r["sifted"] & r["error"]).sum())
            q = (n_err / n_sift * 100) if n_sift > 0 else 50.0
            lo = float(_beta.ppf(0.025, max(n_err, 1), n_sift - n_err + 1)) * 100 if n_sift > 0 else 0.0
            hi = float(_beta.ppf(0.975, n_err + 1, max(n_sift - n_err, 1))) * 100 if n_sift > 0 else 100.0
            q_mc.append(q)
            q_lo_mc.append(max(q - lo, 0))
            q_hi_mc.append(max(hi - q, 0))
        ax.errorbar(levels, q_mc,
                    yerr=[q_lo_mc, q_hi_mc],
                    fmt=mk, color=clr, capsize=3, markersize=6,
                    label=f"d = {d} m", zorder=3)

    ax.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.5,
               label="Shor–Preskill 11%")
    ax.set_xlabel("Oceanic Turbulence Level")
    ax.set_ylabel("QBER (%)")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(["L1\nVery Weak", "L2\nWeak", "L3\nModerate",
                        "L4\nStrong", "L5\nSevere"])
    ax.set_title("QBER vs Turbulence — Clear Ocean, λ = 450 nm")
    ax.legend(loc="upper left", framealpha=0.85)
    _save(fig, "fig4_qber_vs_turbulence.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 5 — Wavelength comparison (bar chart, 3 water types)
# ═══════════════════════════════════════════════════════════════════════════
def fig5_wavelength_comparison():
    print("[Fig 5] Wavelength Comparison — P_click & QBER")
    fig, axes = plt.subplots(1, 3, figsize=(FIGW2 + 2, FIGH))

    turb = 3
    for idx, water in enumerate(WATER_ORDER):
        ax = axes[idx]
        grid = WATER_TYPES[water].d_grid
        # Pick a range ~40% into the span so the link survives at every λ
        d = grid[len(grid) // 4]

        skrs, qbers, pclicks = [], [], []
        lam_labels = []
        for lam in LAMBDA_OPTIONS:
            ch = UWOCChannel(water, float(d), turb, LinkConfig(lam_nm=lam))
            m = ch.mean_metrics()
            pclicks.append(m["p_click"])
            qbers.append(m["qber"] * 100)
            skrs.append(max(0.0, 0.5 * m["p_click"] * (1 - 2 * h2(m["qber"]))))
            lam_labels.append(f"{lam} nm")

        x = np.arange(len(LAMBDA_OPTIONS))
        w = 0.35

        # Bar: P_click
        bars1 = ax.bar(x - w/2, pclicks, w, color=[C_LAM[l] for l in LAMBDA_OPTIONS],
                       edgecolor="k", lw=0.5, label=r"$P_{\rm click}$", alpha=0.8)

        # Secondary axis: QBER
        ax2 = ax.twinx()
        bars2 = ax2.bar(x + w/2, qbers, w, color=[C_LAM[l] for l in LAMBDA_OPTIONS],
                        edgecolor="k", lw=0.5, alpha=0.35, hatch="//")
        ax2.axhline(QBER_LIMIT * 100, color=C_LIMIT, ls="--", lw=1.2)

        ax.set_xticks(x)
        ax.set_xticklabels(lam_labels)
        ax.set_title(f"{WATER_LABELS[water]}\n$d$ = {d} m", fontsize=10)
        ax.set_ylabel(r"$P_{\rm click}$")
        if idx == 2:
            ax2.set_ylabel("QBER (%)")
        ax.grid(True, alpha=0.2, axis="y")

        # Value labels
        for bar, val in zip(bars1, pclicks):
            if val > 1e-6:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                        f"{val:.1e}", ha="center", va="bottom", fontsize=7)

    # Custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#888", edgecolor="k", label=r"$P_{\rm click}$"),
        Patch(facecolor="#888", edgecolor="k", alpha=0.35, hatch="//", label="QBER (%)"),
        Line2D([0], [0], color=C_LIMIT, ls="--", lw=1.2, label="11% bound"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=3,
               framealpha=0.85, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Wavelength Comparison — BB84 UWOC (L3 Turbulence)", fontsize=13, y=1.02)
    fig.tight_layout()
    _save(fig, "fig5_wavelength_comparison.png")


# ═══════════════════════════════════════════════════════════════════════════
# FIGURE 6 — Summary table of maximum secure range (heatmap)
# ═══════════════════════════════════════════════════════════════════════════
def fig6_max_secure_distance():
    print("[Fig 6] Max Secure Distance Table (heatmap)")
    cfg = LinkConfig(lam_nm=450)

    # Compute the d_max matrix
    waters = list(WATER_ORDER)
    levels = list(range(1, 6))
    data = np.zeros((len(waters), len(levels)))

    for i, water in enumerate(waters):
        for j, lv in enumerate(levels):
            try:
                d = max_secure_distance(water, lv, cfg, criterion="mean")
            except Exception:
                d = 0.0
            data[i, j] = d
            print(f"    {WATER_LABELS[water]:15s}  L{lv}: {d:.1f} m")

    fig, ax = plt.subplots(figsize=(FIGW, 3.5))
    im = ax.imshow(data, cmap="YlGnBu", aspect="auto", vmin=0)

    # Labels
    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels([f"L{l}\n{OCEAN_TURB_LEVELS[l]['name']}" for l in levels],
                        fontsize=9)
    ax.set_yticks(range(len(waters)))
    ax.set_yticklabels([WATER_LABELS[w] for w in waters], fontsize=10)

    # Write the value into each cell
    for i in range(len(waters)):
        for j in range(len(levels)):
            val = data[i, j]
            color = "white" if val > data.max() * 0.6 else "black"
            ax.text(j, i, f"{val:.1f} m", ha="center", va="center",
                    fontsize=11, fontweight="bold", color=color)

    ax.set_xlabel("Oceanic Turbulence Level")
    ax.set_title("Maximum Secure Distance $d_{\\rm max}$ (m)\n"
                 "BB84 UWOC, λ = 450 nm, μ = 0.1, QBER < 11%", fontsize=12)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Distance (m)", fontsize=10)
    fig.tight_layout()
    _save(fig, "fig6_max_secure_distance.png")


# ═══════════════════════════════════════════════════════════════════════════
# CSV DATA TABLE
# ═══════════════════════════════════════════════════════════════════════════
def export_csv():
    """Export the Monte-Carlo data table for every configuration to CSV."""
    import csv
    print("\n[CSV] Exporting simulation data table...")
    path = os.path.join(OUT, "sim_results_table.csv")
    cfg = LinkConfig(lam_nm=450)
    turb = 3

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["water", "distance_m", "turb_level", "lambda_nm",
                     "N_qubit", "n_click", "n_sift", "n_err",
                     "P_click", "QBER_pct", "QBER_95pct_upper",
                     "SKR_bits_per_pulse", "secure"])

        for water in WATER_ORDER:
            grid = WATER_TYPES[water].d_grid
            pts = mc_points(water, turb, 450, list(grid), n_qubit=80_000, seed=500)
            for p in pts:
                w.writerow([
                    water, p["d"], turb, 450,
                    80_000, p["n_click"], p["n_sift"], p["n_err"],
                    f"{p['p_click']:.4e}", f"{p['qber']*100:.2f}",
                    f"{p['qber_hi']*100:.2f}",
                    f"{p['skr_per_pulse']:.4e}",
                    "Yes" if p["secure"] else "No"
                ])
    print(f"  ✓ sim_results_table.csv")


# ═══════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 72)
    print("  SINH KET QUA MO PHONG BB84 QUA KENH UWOC -- CHO BAO CAO")
    print("  Mo hinh: composite fading (Beer-Lambert + Gamma scattering")
    print("           + Lognormal/Weibull oceanic turbulence)")
    print("  Tham so: mu=0.1, eta_det=0.18, Y0~1.3e-8, lam=450 nm")
    print("=" * 72)

    fig1_qber_vs_distance()
    fig2_pclick_vs_distance()
    fig3_skr_vs_distance()
    fig4_qber_vs_turbulence()
    fig5_wavelength_comparison()
    fig6_max_secure_distance()
    export_csv()

    print("\n" + "=" * 72)
    print(f"  All figures saved to: {OUT}")
    print("=" * 72)


if __name__ == "__main__":
    main()
