#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
report_diagrams.py — Block diagrams for the report (white background, drawn with matplotlib)

  fig00_system_block.png   block diagram of the UWOC-BB84 emulator on a single FPGA
  fig00_channel_physics.png  the 5 attenuation mechanisms of the underwater optical channel

Run:  python python/report_diagrams.py
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "python", "Images", "report")
os.makedirs(OUT, exist_ok=True)

INK = "#0b0b0b"
INK2 = "#52514e"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
RED = "#b3312c"
GREY = "#8a8a86"

plt.rcParams.update({
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "font.family": "DejaVu Sans", "savefig.dpi": 220,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.15,
})


def box(ax, x, y, w, h, title, lines=(), color=BLUE, fill="#f4f8fd",
        title_size=11, body_size=8.6):
    """Rounded box; the body lines are spaced to fit the box height exactly."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.018",
        linewidth=1.8, edgecolor=color, facecolor=fill, zorder=2))
    ax.text(x + w / 2, y + h - 0.030, title, ha="center", va="top",
            fontsize=title_size, fontweight="bold", color=color, zorder=3)
    if not lines:
        return
    top = y + h - 0.030 - title_size * 0.0042 - 0.028
    step = min(0.049, max(top - y - 0.022, 0.02) / len(lines))
    for i, ln in enumerate(lines):
        ax.text(x + 0.016, top - i * step, ln, ha="left", va="top",
                fontsize=body_size, color=INK2, zorder=3)


def arrow(ax, p0, p1, color=INK2, style="-|>", lw=1.9, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=15, linewidth=lw,
        color=color, linestyle=ls, zorder=1,
        connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))


def elbow(ax, pts, color=INK2, lw=1.9, ls="-"):
    """Polyline with an arrow head on the final segment."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, ls=ls, zorder=1,
            solid_capstyle="round")
    arrow(ax, pts[-2], pts[-1], color=color, lw=lw, ls=ls)


# ═══════════════════════════════════════════════════════════════════════════
def system_block():
    fig, ax = plt.subplots(figsize=(13.0, 6.6))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # khung FPGA
    ax.add_patch(Rectangle((0.010, 0.040), 0.700, 0.845, linewidth=1.6,
                           edgecolor=GREY, facecolor="#fbfbfa",
                           linestyle=(0, (6, 4)), zorder=0))
    ax.text(0.020, 0.905, "FPGA — Altera Cyclone II EP2C20  ·  50 MHz",
            fontsize=11.5, fontweight="bold", color=INK)
    ax.text(0.740, 0.905, "PC (Python)", fontsize=11.5, fontweight="bold",
            color=INK)

    W, H = 0.148, 0.245
    r1, r2, r3 = 0.605, 0.275, 0.070

    box(ax, 0.028, r1, W, H, "1 · TRNG",
        ["4 ring oscillators", "XOR + Von Neumann", "Alice bit/basis, Bob basis"],
        BLUE, body_size=8.2)
    box(ax, 0.196, r1, W, H, "2 · OOK TX",
        ["4-slot frame", "[SYNC][basis][data]", "PWM drive level"],
        BLUE, body_size=8.2)
    box(ax, 0.364, r1, 0.322, H, "3 · UWOC CHANNEL EMULATOR",
        ["ROM: $h_s$ Gamma  ·  $h_o$ Log-normal / Weibull",
         "resampled every $2^{18}$ clk = 5.24 ms ≈ $τ_{coh}$",
         "$p_{sig}$ from $L(d)\\cdot h_s\\cdot h_o$   ·   $e_{pol}(d)$   ·   $Y_0$",
         "click / error: 4 comparators, no divider"],
        ORANGE, "#fef5f1", body_size=8.8)

    box(ax, 0.028, r2, W, H, "4 · Bob RX",
        ["samples slot centres", "basis_match = ~(b⊕b')", "err = match & (a⊕a')"],
        BLUE, body_size=8.2, title_size=10.5)
    box(ax, 0.196, r2, W, H, "5 · Monitor",
        ["window = $2^{16}$ attempts", "QBER · SNR · jitter", "loss · window_valid"],
        AQUA, "#f1faf6", body_size=8.2, title_size=10.5)
    box(ax, 0.364, r2, W, H, "6 · Adaptive ctrl",
        ["4 modes + hysteresis", "λ hill-climbing", "MU_CAP anti-PNS"],
        AQUA, "#f1faf6", body_size=8.2, title_size=10.5)
    box(ax, 0.532, r2, 0.154, H, "7 · UART reporter",
        ["one record per qubit", "115,200 bps"], BLUE, body_size=8.2,
        title_size=10.5)

    box(ax, 0.028, r3, 0.658, 0.140, "System control FSM & timing generator",
        ["slot / frame timing  ·  command FIFO from PC  ·  mode arbitration"],
        GREY, "#f6f6f5", title_size=10.5, body_size=8.4)

    box(ax, 0.740, 0.300, 0.250, 0.480, "PC monitor",
        ["• parse per-qubit records", "• Clopper–Pearson intervals",
         "• QBER / SKR statistics", "• CSV log + plots", "",
         "SKR is computed HERE,", "not on-chip"],
        RED, "#fdf3f2", body_size=9.0)

    # ---- forward path ----
    y1, y2 = r1 + H / 2, r2 + H / 2
    arrow(ax, (0.176, y1), (0.196, y1))
    arrow(ax, (0.344, y1), (0.364, y1))
    arrow(ax, (0.176, y2), (0.196, y2))
    arrow(ax, (0.344, y2), (0.364, y2))
    arrow(ax, (0.512, y2), (0.532, y2))
    arrow(ax, (0.686, y2), (0.740, y2), color=RED)
    ax.text(0.713, y2 + 0.020, "UART", ha="center", fontsize=9, color=RED)

    # ---- channel → Bob (left dog-leg) ----
    elbow(ax, [(0.400, r1), (0.400, 0.560), (0.102, 0.560), (0.102, r2 + H)],
          color=ORANGE)
    ax.text(0.250, 0.568, "photon click / bit error", ha="center", va="bottom",
            fontsize=8.8, color=ORANGE)

    # ---- feedback control loop ----
    elbow(ax, [(0.438, r2 + H), (0.438, 0.575), (0.640, 0.575),
               (0.640, r1)], color=AQUA)
    ax.text(0.520, 0.578, "control loop: drive · basis · slot · λ",
            ha="center", va="bottom", fontsize=8.6, color=AQUA,
            style="italic")

    arrow(ax, (0.102, r2), (0.102, r3 + 0.140), color=GREY, ls=":")

    ax.set_title("Single-FPGA real-time UWOC-BB84 emulator with closed-loop "
                 "adaptive control",
                 fontsize=14.5, fontweight="bold", color=INK, pad=14)
    fig.savefig(os.path.join(OUT, "fig00_system_block.png"))
    plt.close(fig)
    print("   saved  fig00_system_block.png")


# ═══════════════════════════════════════════════════════════════════════════
def channel_physics():
    fig, ax = plt.subplots(figsize=(12.4, 4.4))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    ax.add_patch(Rectangle((0.172, 0.16), 0.656, 0.60, linewidth=1.5,
                           edgecolor=BLUE, facecolor="#eef5fd",
                           linestyle=(0, (5, 4)), zorder=0))
    ax.text(0.5, 0.895, "Underwater channel", ha="center", fontsize=12.5,
            fontweight="bold", color=BLUE)

    box(ax, 0.008, 0.30, 0.150, 0.36, "ALICE",
        ["weak coherent source", "μ = 0.1 photon/pulse", "λ = 450/532/650 nm"],
        INK, "#f4f4f3", title_size=12, body_size=8.4)
    box(ax, 0.842, 0.30, 0.150, 0.36, "BOB",
        ["single-photon detector", "η = 0.18", "Y₀ = 1.3e-5"],
        INK, "#f4f4f3", title_size=12, body_size=8.4)

    ax.annotate("", xy=(0.840, 0.46), xytext=(0.160, 0.46),
                arrowprops=dict(arrowstyle="-|>", lw=3.2, color=AQUA,
                                mutation_scale=22, alpha=0.55))

    items = [
        ("Absorption", "energy absorbed by\nwater + particles", "$L(d)$", 0.246),
        ("Scattering", "photons deflected\nout of the beam", "$h_s\\!\\sim$ Gamma", 0.376),
        ("Turbulence", "refractive-index\nfluctuations", "$h_o\\!\\sim$ LN/Weib.", 0.506),
        ("Depolarization", "multiple scattering\nrotates polarization", "$e_{pol}(d)$", 0.636),
        ("Detector noise", "dark counts +\nbackground light", "$Y_0$", 0.766),
    ]
    for name, desc, sym, x in items:
        ax.text(x, 0.815, name, ha="center", fontsize=10,
                fontweight="bold", color=INK)
        ax.text(x, 0.752, desc, ha="center", va="top", fontsize=8.2,
                color=INK2, linespacing=1.35)
        ax.text(x, 0.245, sym, ha="center", fontsize=10.5, color=RED,
                fontweight="bold")
        ax.plot([x, x], [0.305, 0.58], color=GREY, lw=0.9, ls=":")

    ax.text(0.5, 0.075,
            r"$h(d,t) = L(d,\lambda,\mathrm{water}) \cdot h_s(d,t) \cdot h_o(d,t)$"
            "        with        "
            r"$\bar n = \mu \, L \, h \, \eta_{det}$,     "
            r"$P_{click} = 1-(1-Y_0)e^{-\bar n}$",
            ha="center", fontsize=12, color=INK)

    ax.set_title("Five impairments of the underwater optical channel — "
                 "all five enter the hardware model",
                 fontsize=13.5, fontweight="bold", color=INK, pad=10)
    fig.savefig(os.path.join(OUT, "fig00_channel_physics.png"))
    plt.close(fig)
    print("   saved  fig00_channel_physics.png")


if __name__ == "__main__":
    system_block()
    channel_physics()
