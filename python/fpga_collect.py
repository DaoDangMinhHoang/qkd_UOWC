#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fpga_collect.py — Collects BB84/UWOC data on the FPGA for the paper
═══════════════════════════════════════════════════════════════════════════════

DIFFERENT from bb84_uwoc_measure.py: that script sweeps fast to LOOK; this one
runs LONG to PRODUCE PUBLISHABLE DATA, so it has three things the other lacks:

  [1] A DUAL BUDGET per measurement point — stop on ENOUGH SAMPLES (n_sift ≥
      target) or on TIME OUT (cap), whichever comes first. Underwater P_click falls
      ~2 decades across the range of interest, so a fixed qubit count would either
      waste hours on the near points or never finish the far ones.
  [2] CHECKPOINTING — every finished point writes a CSV row immediately. A re-run
      skips points already present. A power cut at 3am does not lose the whole session.
  [3] PER-CLICK LOGGING — irrad (SNR proxy) + bmatch + err for every click, so the
      sliding-window / vs-SNR QBER figures (like Fig. 3 of the previous paper) can be built.

Run:
    python python/fpga_collect.py --port COM10 --phase fixed
    python python/fpga_collect.py --port COM10 --phase adaptive   # after flipping SW[1]=1

⚠ --chunk is always 1. The bitstream currently on the board has NO command FIFO;
  sending back-to-back loses commands and drives P_click down ~0.4× (see tb_cmd_fifo.v).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                          # noqa: E402

from bb84_uwoc_measure import (                             # noqa: E402
    CONF, MIN_SIFT, QBER_LIMIT, WATER_ORDER, _parse_full, qber_upper,
)
from uwoc_channel_model import (                            # noqa: E402
    LAMBDA_OPTIONS, WATER_TYPES, LinkConfig, UWOCChannel, h2,
)

import serial                                               # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data")
POINTS_CSV = os.path.join(DATA_DIR, "fpga_points.csv")

POINT_FIELDS = [
    "tag", "phase", "water", "dist_idx", "distance_m", "turb", "lam_nm",
    "n_qubit", "n_click", "n_sift", "n_err", "p_click", "sift_eff",
    "qber", "qber_hi", "secure", "skr_per_pulse", "seconds", "rate_qps",
    "p_click_model", "qber_model", "timestamp",
]


# ═══════════════════════════════════════════════════════════════════════════
# Link to the FPGA
# ═══════════════════════════════════════════════════════════════════════════
class Link:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.004):
        # 4 ms: calibrated on COM10 — 86.6 qubits/s, and the P_click obtained is
        # 104% of the model value, so this timeout does NOT cut clicks off.
        self.timeout = timeout
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.5)
        self.ser.reset_input_buffer()

    def configure(self, water: int, dist: int, turb: int, lam: int):
        for b in (0x30 | (dist & 0x0F),
                  0x40 | ((water & 0x3) << 2) | (lam & 0x3),
                  0x50 | (turb & 0x07),
                  0x01):
            self.ser.write(bytes([b]))
            time.sleep(0.02)
        time.sleep(0.05)
        self.ser.reset_input_buffer()

    def run_point(self, rng, target_sift: int, cap_s: float, p_basis_z=0.5,
                  progress_every=20.0):
        """Run until target_sift sifted bits are collected, or cap_s seconds elapse."""
        n = n_click = n_sift = n_err = 0
        clicks = []
        t0 = time.perf_counter()
        t_next = progress_every

        while True:
            el = time.perf_counter() - t0
            if n_sift >= target_sift or el >= cap_s:
                break

            ad = int(rng.integers(0, 2))
            ab = 0 if rng.random() < p_basis_z else 1
            bb = 0 if rng.random() < p_basis_z else 1
            self.ser.write(bytes([0x80 | (ad << 2) | (ab << 1) | bb]))
            n += 1

            r = _parse_full(self.ser.readline().decode("ascii", "ignore"))
            if r is not None:
                n_click += 1
                clicks.append(r)
                if r["bmatch"]:
                    n_sift += 1
                    n_err += r["err"]

            if el >= t_next:
                t_next += progress_every
                print("\r      %6.1f s  n=%d  click=%d  sift=%d  err=%d   "
                      % (el, n, n_click, n_sift, n_err), end="", flush=True)

        # Drain whatever lines are still stuck in the USB-serial buffer
        self.ser.timeout = 0.2
        while True:
            r = _parse_full(self.ser.readline().decode("ascii", "ignore"))
            if r is None:
                break
            n_click += 1
            clicks.append(r)
            if r["bmatch"]:
                n_sift += 1
                n_err += r["err"]
        self.ser.timeout = self.timeout

        el = time.perf_counter() - t0
        print("\r" + " " * 62 + "\r", end="")
        return dict(n_qubit=n, n_click=n_click, n_sift=n_sift, n_err=n_err,
                    seconds=el, clicks=clicks)

    def close(self):
        self.ser.close()


# ═══════════════════════════════════════════════════════════════════════════
# Check the switch state before spending hours on a run
# ═══════════════════════════════════════════════════════════════════════════
def check_switches(link: Link, rng, n=8000) -> float:
    """Return the ratio P_click(λ=450)/P_click(λ=650) in clear ocean, d = 5 m.

    cfg_lambda ONLY takes effect when adaptive is off (top_module.v:133 —
    active_lambda = adaptive_enable ? adapt_lambda : cfg_lambda). Hence:
        ratio ≈ 3.0  ⇒ SW[1] = 0, fixed mode, cfg_lambda is in effect.
        ratio ≈ 1.0  ⇒ adaptive is overriding λ, so "wavelength sweep" data is meaningless.
    The value 3.05 comes from psig_rom: 1.038e-2 (450 nm) vs 3.40e-3 (650 nm).
    """
    out = []
    for lam in (0, 2):
        link.configure(0, 0, 5, lam)
        c = 0
        for i in range(n):
            ad = int(rng.integers(0, 2))
            link.ser.write(bytes([0x80 | (ad << 2) | (i & 0x03)]))
            if _parse_full(link.ser.readline().decode("ascii", "ignore")):
                c += 1
        out.append(c)
        print("      λ = %d nm : %d click / %d = %.3e"
              % (LAMBDA_OPTIONS[lam], c, n, c / n))
    return (out[0] / max(out[1], 1))


# ═══════════════════════════════════════════════════════════════════════════
# Measurement matrix
# ═══════════════════════════════════════════════════════════════════════════
def build_matrix(phase: str):
    """(tag, water, dist_idx, turb, lam, target_sift, cap_seconds)

    The time cap comes from psig_rom's P_click and the measured rate of 86.6 qubits/s.
    Far points never reach the target — that is deliberate: the Clopper-Pearson upper
    bound then says outright that the sample is small, instead of faking a QBER.
    """
    M = []

    # ---- A. QBER/SKR vs range — the headline figure --------------------
    # clear ocean, turbulence L5, 450 nm
    for di, cap in ((0, 900), (1, 1500), (2, 2100), (3, 2100),
                    (4, 2100), (5, 2100)):
        M.append(("A_dist_d%d" % di, 0, di, 5, 0, 400, cap))

    # ---- B. QBER vs turbulence level, fixed range -----------------------
    # Expectation: the MEAN QBER stays nearly constant (P_click is linear in h,
    # so the expectation cancels the fading). Measuring that is itself a result.
    for lv in range(1, 6):
        M.append(("B_turb_L%d" % lv, 0, 0, lv, 0, 400, 720))

    # ---- C. Optimal wavelength depends on the water type ----------------
    # clear ocean favours blue; turbid harbour shifts to red (450:5.1e-3 < 650:7.8e-3).
    for li in range(3):
        M.append(("C_lam_clear_%d" % LAMBDA_OPTIONS[li], 0, 0, 3, li, 400, 720))
    for li in range(3):
        M.append(("C_lam_harbor_%d" % LAMBDA_OPTIONS[li], 2, 0, 3, li, 400, 720))

    # ---- D. Comparison of the three water types ------------------------
    for di in (1, 2, 3):
        M.append(("D_coastal_d%d" % di, 1, di, 3, 0, 400, 900))
    for di in (1, 2, 3):
        M.append(("D_harbor_d%d" % di, 2, di, 3, 0, 400, 900))

    return [("%s_%s" % (phase, m[0]),) + tuple(m[1:]) for m in M]


# ═══════════════════════════════════════════════════════════════════════════
def model_expect(water: str, d: float, turb: int, lam_nm: int):
    cfg = LinkConfig(lam_nm=lam_nm)
    m = UWOCChannel(water, d, turb, cfg).mean_metrics()
    return m["p_click"], m["qber"]


def load_done():
    if not os.path.exists(POINTS_CSV):
        return set()
    with open(POINTS_CSV, newline="", encoding="utf-8") as f:
        return {r["tag"] for r in csv.DictReader(f)}


def append_point(row):
    new = not os.path.exists(POINTS_CSV)
    with open(POINTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=POINT_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def save_clicks(tag, clicks):
    p = os.path.join(DATA_DIR, "clicks_%s.csv" % tag)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["a_data", "a_basis", "b_basis",
                                          "bob", "bmatch", "err", "irrad"])
        w.writeheader()
        w.writerows(clicks)


def main():
    ap = argparse.ArgumentParser(description="Thu số liệu BB84/UWOC trên FPGA")
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--timeout", type=float, default=0.004)
    ap.add_argument("--phase", default="fixed", choices=("fixed", "adaptive"))
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--skip-check", action="store_true",
                    help="bỏ qua bước kiểm tra SW[1] (~3 phút)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="nhân trần thời gian và chia mục tiêu số mẫu. "
                         "Dùng --scale 0.01 để chạy thử toàn bộ ma trận trong "
                         "vài phút trước khi giao máy cho phiên qua đêm.")
    ap.add_argument("--out", default=None,
                    help="thư mục số liệu (mặc định <repo>/data)")
    args = ap.parse_args()

    global DATA_DIR, POINTS_CSV
    if args.out:
        DATA_DIR = os.path.abspath(args.out)
        POINTS_CSV = os.path.join(DATA_DIR, "fpga_points.csv")

    os.makedirs(DATA_DIR, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    link = Link(args.port, args.baud, args.timeout)

    matrix = [(t, wi, di, tb, li,
               max(1, int(tg * args.scale)), max(2.0, cap * args.scale))
              for (t, wi, di, tb, li, tg, cap) in build_matrix(args.phase)]
    done = load_done()
    todo = [m for m in matrix if m[0] not in done]

    print("█" * 78)
    print("  THU SỐ LIỆU FPGA — pha '%s', cổng %s" % (args.phase, args.port))
    print("  %d điểm, %d đã có, %d cần chạy" % (len(matrix), len(matrix) - len(todo),
                                                len(todo)))
    print("  trần thời gian tổng: %.1f giờ" % (sum(m[6] for m in todo) / 3600))
    print("█" * 78)

    try:
        if not args.skip_check:
            print("\n  Kiểm tra SW[1] (adaptive) qua độ nhạy của cfg_lambda...")
            ratio = check_switches(link, rng)
            print("      tỉ số P_click(450)/P_click(650) = %.2f  (fixed ⇒ ~3.0)"
                  % ratio)
            if args.phase == "fixed" and ratio < 1.8:
                print("\n  ✗ DỪNG: λ không ảnh hưởng P_click ⇒ SW[1] đang BẬT.")
                print("    Gạt SW[1] = 0 rồi chạy lại, hoặc dùng --phase adaptive.")
                return
            if args.phase == "adaptive" and ratio > 1.8:
                print("\n  ✗ DỪNG: λ vẫn ảnh hưởng P_click ⇒ SW[1] đang TẮT.")
                print("    Gạt SW[1] = 1 rồi chạy lại.")
                return
            print("      ✓ trạng thái công tắc khớp với pha '%s'" % args.phase)

        t_start = time.perf_counter()
        for k, (tag, wi, di, turb, li, target, cap) in enumerate(todo, 1):
            water = WATER_ORDER[wi]
            d = float(WATER_TYPES[water].d_grid[di])
            lam = LAMBDA_OPTIONS[li]
            print("\n  [%d/%d] %s — %s, d = %g m, L%d, λ = %d nm "
                  "(mục tiêu %d sift, trần %.0f phút)"
                  % (k, len(todo), tag, WATER_TYPES[water].name, d, turb, lam,
                     target, cap / 60))

            link.configure(wi, di, turb, li)
            r = link.run_point(rng, target, cap)

            q = r["n_err"] / r["n_sift"] if r["n_sift"] else 0.5
            q_hi = qber_upper(r["n_err"], r["n_sift"])
            secure = (r["n_sift"] >= MIN_SIFT) and (q_hi < QBER_LIMIT)
            pc_m, q_m = model_expect(water, d, turb, lam)

            row = dict(
                tag=tag, phase=args.phase, water=water, dist_idx=di,
                distance_m=d, turb=turb, lam_nm=lam,
                n_qubit=r["n_qubit"], n_click=r["n_click"],
                n_sift=r["n_sift"], n_err=r["n_err"],
                p_click=r["n_click"] / max(r["n_qubit"], 1),
                sift_eff=r["n_sift"] / max(r["n_qubit"], 1),
                qber=q, qber_hi=q_hi, secure=secure,
                skr_per_pulse=((r["n_sift"] / max(r["n_qubit"], 1))
                               * max(0.0, 1 - 2 * h2(q_hi)) if secure else 0.0),
                seconds=r["seconds"], rate_qps=r["n_qubit"] / max(r["seconds"], 1e-9),
                p_click_model=pc_m, qber_model=q_m,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            append_point(row)
            save_clicks(tag, r["clicks"])

            print("        n=%d  click=%d (P=%.3e, mô hình %.3e)  sift=%d  err=%d"
                  % (r["n_qubit"], r["n_click"], row["p_click"], pc_m,
                     r["n_sift"], r["n_err"]))
            print("        QBER = %.2f%%  (cận trên %.0f%% = %.2f%%, mô hình %.2f%%)  %s"
                  % (q * 100, CONF * 100, q_hi * 100, q_m * 100,
                     "an toàn" if secure else "KHÔNG/thiếu mẫu"))
            print("        %.1f phút, còn lại ~%.1f giờ"
                  % (r["seconds"] / 60,
                     sum(m[6] for m in todo[k:]) / 3600))

        print("\n  Xong. Tổng %.2f giờ. Số liệu ở %s"
              % ((time.perf_counter() - t_start) / 3600, DATA_DIR))
    finally:
        link.close()


if __name__ == "__main__":
    main()
