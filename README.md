# FPGA-Based Adaptive BB84 QKD — Underwater (UWOC)

Real-time optimization of photon intensity, basis bias and wavelength for Quantum Key
Distribution over underwater optical links, implemented on Altera Cyclone II FPGA.

## Overview

This project implements a complete BB84 QKD system on FPGA with a closed-loop adaptive
controller that dynamically adjusts transmission parameters in response to channel
conditions, plus an on-chip channel emulator for real-time testing without optical hardware.

### Channel Model

The underwater channel model includes geometric path loss, scattering-induced fading, and oceanic turbulence:

| Metric | Underwater (UWOC) |
|---|---|══════════════════════════════════════════════════════════════════════════════════
  QUÉT CỰ LY — Clear ocean, nhiễu loạn L1
══════════════════════════════════════════════════════════════════════════════════
  c(λ) = 0.151 m⁻¹, λ = 450 nm, batch = 20000
  cấu hình                     click   sift    P_click     QBER   ±sai số   SKR/xung    kết luận      
  ------------------------------------------------------------------------------------
  d = 5 m                        205     96  1.025e-02    0.00%     0.00%  4.800e-03     an toàn
  d = 15 m                        52     30  2.600e-03    0.00%     0.00%  1.500e-03     an toàn
      [4500/20000] 72 q/s  click=3
| Channel model | `h = L(d,λ,water)·h_s·h_o` |
| Turbulence | Nikishov spectrum (ε, χ_T, w) |
| Fading distributions | Gamma (scattering) × Lognormal/Weibull (oceanic) |
| Dominant impairment | **photon loss** + polarization error |
| Detection layer | μ, η_det, dark/background, P_click, e_pol |
| Adaptive knobs | power, basis bias, slot width, **wavelength** (450/532/650 nm) |
| RTL | `uwoc_channel.v` |

### Physics Model in One Line

```
h = L · h_s · h_o        L = D²/(π(d·tanθ)²) · exp(−F·c(λ)·d)      [Beer-Lambert + geometric]
                         h_s ~ Gamma(1/σ_s², σ_s²)                 [scattering-induced fading]
                         h_o ~ Lognormal (σ²<1) / Weibull (σ²≥1)   [oceanic turbulence]

n̄ = μ·h·η_det            P_click = 1 − (1−Y₀)·e^(−n̄)
QBER = [e_pol·(1 − e^(−n̄)) + ½·Y₀] / P_click
```

References: Kebapci et al. *IEEE Photonics J.* 15(4) 2023; Salcedo-Serrano et al. *IEEE ICC*
2022; Jamali, Akhoundi & Salehi *IEEE TWC* 15(6) 2016.

### Workflow

```bash
# 1. Verify the physics model numerically (7 quantitative self-tests)
python python/uwoc_channel_model.py
python python/uwoc_channel_model.py --plot

# 2. Generate FPGA ROMs from the verified model
python python/uwoc_lut_gen.py --verify        # → verilog/uwoc_channel_rom.vh

# 3. Simulate the RTL against the Python golden model
vlog +incdir+verilog verilog/uwoc_channel.v verilog/tb_uwoc_channel.v
vsim -c -do "run -all; quit" tb_uwoc_channel

# 4. Simulate the closed adaptive loop
vlog +incdir+verilog verilog/channel_monitor.v verilog/adaptive_controller.v \
                     verilog/tb_adaptive_loop.v
vsim -c -do "run -all; quit" tb_adaptive_loop

# 5. Check that a burst of UART qubit commands loses nothing
vlog +incdir+verilog verilog/*.v
vsim -c -GN_CMD=32 -do "run -all; quit" tb_cmd_fifo

# 6. Measure (simulation or real FPGA)
python python/bb84_uwoc_measure.py --simulate --scan distance
python python/bb84_uwoc_measure.py --port COM28 --scan wavelength --batch 50000
```

> **Coupling to watch:** `channel_monitor.v`'s `NEXP_LOG2` parameter must equal
> `log2(--window)` used in `uwoc_lut_gen.py` (default 16 ↔ 65536). The `nexp_inv` ROM that
> normalizes SNR is generated for that specific window size.

> **Sample size, not a clean channel.** A row reading `QBER = 0.00%` almost always means
> too few sifted bits, not a perfect link — at `d = 5 m` the model predicts QBER ≈ 1.64%,
> so 93 sifted bits yield 0 errors 21% of the time. The measurement script reports a
> one-sided Clopper–Pearson upper bound and only calls a point "secure" when that bound
> stays below 11%. Budget `n_sift ≳ 1000`, i.e. `batch ≳ 1000/(P_click·q_basis)`.

### Three findings that drove the design

1. **Large monitoring window is required.** With P_click ~ 10⁻³ in underwater links, small windows result in per-window QBER that is pure shot noise. The window is set to 2¹⁶ and gated by `window_valid`.
2. **Turbulence does not show up in mean QBER.** Across different turbulence levels, the mean QBER moves significantly less than the *between-window standard deviation* — because P_click is near-linear in `h`, so expectation cancels fading. Hence `qber_jitter` was added; without it the controller is blind to turbulence.
3. **`loss_rate` cannot indicate a dead link** — it saturates at 255 even on a perfectly healthy link due to the high attenuation of water. Link-death detection uses zero photon count instead.

### Architecture

```
TRNG ×3 → Alice → OOK TX → PWM → UWOC Emulator → OOK RX → Bob
                                                                     ↓
   ┌─── basis_prob ──── slot_width ──── power_level ←── Adaptive ← Error Est.
   ↓         ↓               ↓              ↓          Controller     ↓
 Alice    OOK TX/RX       OOK TX/RX        PWM       (Wavelength) ↑ Channel
                                                         Monitor → UART → PC
```

## Hardware Platform

- **FPGA:** Altera Cyclone II EP2C20F484C7
- **Board:** Terasic DE1 Development Board
- **Clock:** 50 MHz
- **Interface:** RS-232 (115200 baud) for data logging
- **Resource Usage:** 4,600 / 18,752 LEs (24.5%), 1 multiplier, Fmax = 63.74 MHz

## Project Structure

```
├── verilog/                    # RTL source
│   ├── top_module.v            # Top-level with BB84 FSM
│   ├── alice.v                 # BB84 encoder
│   ├── bob.v                   # BB84 decoder
│   ├── trng.v                  # Ring oscillator TRNG (4 ROs + Von Neumann)
│   ├── trng_random.v           # TRNG wrapper (drop-in for LFSR)
│   ├── ook_tx_serializer.v     # OOK modulator (4-slot framing)
│   ├── ook_rx_deserializer.v   # OOK demodulator (edge-triggered sync)
│   ├── pwm_and_basis.v         # PWM power control + biased basis selector
│   ├── uwoc_channel.v          # Underwater channel emulator
│   ├── uwoc_channel_rom.vh     # ROMs — GENERATED, never edit by hand
│   ├── tb_uwoc_channel.v       # TB: channel vs Python golden model
│   ├── tb_adaptive_loop.v      # TB: closed adaptive loop
│   ├── tb_cmd_fifo.v           # TB: no qubit command is dropped on a UART burst
│   ├── error_estimation.v      # Sifting and error detection
│   ├── channel_monitor.v       # Window QBER/SNR/jitter/loss estimator
│   ├── adaptive_controller.v   # 4-mode FSM + wavelength hill-climbing
│   ├── uart_tx.v               # UART transmitter
│   ├── uart_rx.v               # UART receiver
│   └── uart_reporter.v         # Per-qubit and per-window packet formatter
│
├── constraints/
│   └── bb84_phase2.sdc         # Timing constraints (false paths for TRNG ROs)
│
├── python/                     # Measurement and visualization scripts
│   ├── uwoc_channel_model.py   # UWOC physics + 7 numerical self-tests
│   ├── uwoc_lut_gen.py         # Generates verilog/uwoc_channel_rom.vh
│   ├── bb84_uwoc_measure.py    # Measurement scans (FPGA or simulation)
│   ├── fpga_collect.py         # Long-run FPGA collection (checkpointed)
│   ├── check_vs_theory.py      # Statistical tests: measurement vs model
│   └── paper_figs_uwoc.py      # Publication figures from collected data
│
├── docs/
│   └── bao_cao_lab_uwoc_v2.md  # Slide script for the lab report
│
└── README.md
```
*(Note: Legacy FSO files such as `gamma_gamma_final.v` and `bb84_fpga_qber_snr_5_level.py` are present in the repository but omitted from this UWOC-focused tree.)*

## Adaptive Controller

Four operating modes. SNR is **normalized** (128 = the link's nominal click rate), so the
static path loss `exp(−c·d)` is divided out and the controller sees only the fading margin.

| Mode | QBER | SNR (norm.) | Jitter | μ | Basis (p_z) | Slot | Strategy |
|------|------|------|------|------|------|------|------|
| **Aggressive** | < 4% | ≥ 160 | < 6 | 6/15 | 50% | 5 ms | Max throughput |
| **Moderate** | < 8% | ≥ 96 | — | 9/15 | 60% | 10 ms | Balanced |
| **Conservative** | < 15% | > 40 | ≥ 16 | 12/15 | 80% | 50 ms | Max reliability |
| **Pause** | ≥ 15% | ≤ 40 | — | — | — | — | Suspend TX |

- **Hysteresis:** downgrade immediate (security-first); upgrade needs 3 good windows.
- **`window_valid` gate:** if a window has < 16 sifted detections its QBER is shot noise, so
  the mode is *held* rather than changed.
- **Jitter gate:** `qber_jitter` (EWMA of |ΔQBER|) is the turbulence indicator. Threshold 16
  (±8%) sits well above the ~3–4 unit shot-noise floor of that statistic.
- **μ capped at 12/15:** raising μ lowers QBER but raises the multi-photon fraction; the huge
  underwater loss makes a PNS attack easier to hide, so intensity is bounded.
- **Wavelength hill-climbing:** probes neighbouring λ, accumulating click counts over 4
  windows per measurement and accepting a candidate only beyond a 1/16 margin (≈3σ). An
  escape path cycles λ if the link goes silent, so the climber cannot strand itself on a λ
  that kills the link.

## UWOC Channel Emulator

Hardware implementation of `h = L · h_s · h_o` plus a photon-detection layer:

- **ROM-based inverse CDF**: 256×12-bit per distribution (8 scattering classes + 6 turbulence levels)
- **12-bit `h` (256 = 1.0)** — avoids truncation issues and preserves heavy tails of Gamma/Weibull.
- **24-bit probabilities** — prevents rounding P_sig down to zero at long ranges.
- **Coherence-time sampling** (2¹⁸ cycles ≈ 5.2 ms) — ensures fading acts over meaningful durations rather than averaging out inside a monitoring window.
- **~52 kbit ROM** (13 of 52 M4K blocks on EP2C20), 2 multipliers
- **Loss semantics:** no-click silences the whole OOK frame → RX timeout → `evt_qubit_lost`;
  a polarization error flips **only the data slot**, leaving SYNC and basis slots intact.

## Quick Start

### Run on FPGA

1. Open project in Quartus II 13.0
2. Compile and program the DE1 board
3. Set DIP switches:
   - `SW[9]` = 1 (PC input mode)
   - `SW[4]` = 1 (turbulence ON)
   - `SW[7:5]` = turbulence level (001–101)
   - `SW[1]` = 0 (fixed) or 1 (adaptive)
   - `SW[0]` = 0 (auto mode)
4. Connect RS-232 and run:

```bash
python python/bb84_uwoc_measure.py --port COM28 --scan distance
```

### Run Simulation (no hardware needed)

```bash
# Sweep parameters to analyze performance
python python/bb84_uwoc_measure.py --simulate --scan distance
python python/bb84_uwoc_measure.py --simulate --scan wavelength
```

### Requirements

```bash
pip install numpy matplotlib scipy pyserial
```

## Switch Configuration

| Switch | Function | Values |
|--------|----------|--------|
| `SW[9]` | PC input mode | 0 = autonomous, 1 = PC control |
| `SW[7:5]` | Turbulence level | 000=OFF, 001=Weak, ..., 101=Severe |
| `SW[4]` | Turbulence enable | 0 = bypass, 1 = enabled |
| `SW[1]` | Adaptive control | 0 = fixed params, 1 = adaptive |
| `SW[0]` | Auto/manual | 0 = auto run, 1 = manual (KEY[1]) |
| `KEY[3]` | Reset | Press to reset all modules |
| `KEY[0]` | Eavesdropper | Hold to simulate intercept-resend |

## LED Indicators

| LED | Function |
|-----|----------|
| `LEDR[1:0]` | TX qubit (basis, data) |
| `LEDR[3:2]` | RX qubit |
| `LEDR[4]` | TX active |
| `LEDR[5]` | RX active |
| `LEDR[6]` | Signal detect |
| `LEDR[7]` | Basis match |
| `LEDG[1:0]` | Adaptive mode (00=AGG, 01=MOD, 10=CON, 11=PAU) |
| `LEDG[6]` | Adaptive enabled |

## UART Protocol

**PC → FPGA** (1 byte):
- Bit[7] = 1: Qubit command — Bit[2]=alice_data, Bit[1]=alice_basis, Bit[0]=bob_basis
- `0x01`: Reset statistics
- `0x02`: Request status

**FPGA → PC** (per-qubit response):
```
@<a_data>,<a_basis>,<b_basis>,<bob_bit>,<basis_match>,<error>,<irradiance>,<total_hex>,<sifted_hex>,<errors_hex>*\r\n
```

## Timing Constraints

The TRNG uses intentional ring oscillator combinational loops for entropy generation. The SDC file (`bb84_phase2.sdc`) declares false paths for these loops:

```tcl
set_false_path -from [get_keepers {*trng_core*ro*_chain*}]
```

After applying constraints: Setup Slack = +4.312 ns, Fmax = 63.74 MHz.

## License

This project is developed at Hanoi University of Science and Technology (HUST) under project T2025-PC-068. Please contact the authors for licensing information.
