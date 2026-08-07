<div align="center">

# Adaptive BB84 QKD over an Underwater Optical Channel

**A single-FPGA, real-time emulator and closed-loop controller for discrete-variable Quantum Key Distribution (QKD) through water.**

[![Platform](https://img.shields.io/badge/FPGA-Altera%20Cyclone%20II%20EP2C20-blue)](#hardware-platform--configuration)
[![Toolchain](https://img.shields.io/badge/Quartus%20II-13.0-orange)](#getting-started)
[![HDL](https://img.shields.io/badge/HDL-Verilog--2001-lightgrey)](#repository-structure)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB)](#prerequisites)
[![License](https://img.shields.io/badge/License-Academic%2FResearch-red.svg)](#license)

<br />
<img src="python/Images/report/fig00_system_block.png" alt="System block diagram" width="800"/>
</div>

---

## 📖 Table of Contents

- [About The Project](#about-the-project)
  - [Key Features](#key-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Simulation Only (No Hardware)](#simulation-only--no-hardware)
  - [Running on Hardware](#running-on-hardware)
- [System Architecture](#system-architecture)
  - [Adaptive Controller](#adaptive-controller)
  - [UWOC Channel Emulator](#uwoc-channel-emulator)
- [Key Results](#key-results)
- [Physics Model & Design Insights](#physics-model--design-insights)
- [Hardware Reference](#hardware-reference)
  - [Hardware Platform & Configuration](#hardware-platform--configuration)
  - [UART Protocol](#uart-protocol)
  - [Timing Constraints](#timing-constraints)
- [Repository Structure](#repository-structure)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)

---

## 🚀 About The Project

Underwater optical links present a fundamentally different regime from atmospheric free-space optics (FSO). Attenuation is three orders of magnitude higher, the dominant impairment is **photon loss** rather than bit flips, and turbulence hides in the *variance* between observation windows rather than in the mean error rate. Control policies tuned for atmospheric FSO do not transfer effectively.

This repository provides a complete, robust hardware testbed designed specifically for this challenging regime:

- **Synthesizable UWOC Channel Emulator** (`uwoc_channel.v`): Implements composite fading $h = L(d,\lambda,\text{water}) \cdot h_s \cdot h_o$ plus a photon-detection stage, driven by ROMs generated from a numerically validated physics model.
- **Closed-Loop Adaptive Controller** (`adaptive_controller.v`): Retunes photon intensity, basis bias, slot width, and **wavelength** in real-time from on-chip channel telemetry.
- **Validated Python Model** (`uwoc_channel_model.py`): The source of the FPGA ROMs and the golden reference against which the RTL is verified.

Everything runs on a single Cyclone II device at 50 MHz—requiring no physical optical hardware to exercise the full control loop.

### ✨ Key Features

- **Real-Time Emulation:** Accurately simulates the underwater channel physics on-chip.
- **Adaptive Parameter Control:** Automatically adjusts link parameters to maximize throughput and ensure security under changing channel conditions.
- **Wavelength Hill-Climbing:** Probes and selects optimal wavelengths dynamically.
- **Robust UART Telemetry:** High-speed, buffered data collection directly to a host PC.

> [!NOTE]  
> **All performance numbers in this README are Monte-Carlo simulation results**, produced by `python/report_sim_figs.py` from the same channel model that populates the FPGA ROMs. The measurement scripts (`bb84_uwoc_measure.py`, `fpga_collect.py`) fully support real hardware over UART, but no hardware campaign data is included in this repository.

---

## 🛠 Getting Started

Follow these steps to set up the project locally for simulation or hardware deployment.

### Prerequisites

Ensure you have Python 3.8+ installed. The following Python packages are required:

```bash
pip install numpy scipy matplotlib pyserial python-pptx
```
*(Note: `pyserial` is only needed for hardware measurement; `python-pptx` is only for the report generator. Simulation needs just NumPy, SciPy, and Matplotlib.)*

### Simulation Only (No Hardware)

You can run the entire model validation and simulation suite without an FPGA:

```bash
# 1. Validate the physics model
python python/uwoc_channel_model.py                        

# 2. Run simulations across various parameters
python python/bb84_uwoc_measure.py --simulate --scan distance
python python/bb84_uwoc_measure.py --simulate --scan turbulence
python python/bb84_uwoc_measure.py --simulate --scan wavelength
python python/bb84_uwoc_measure.py --simulate --scan mu

# 3. Regenerate all figures
python python/report_sim_figs.py                           
```

### Running on Hardware

To deploy the design to the Terasic DE1 board:

1. Open `verilog/top_module.qpf` in **Quartus II 13.0**.
2. Compile the design and program the DE1 board.
3. Configure the DIP switches (see [Hardware Platform & Configuration](#hardware-platform--configuration) below).
4. Press `KEY[3]` to reset the system.
5. Run the measurement scripts on your host PC:

```bash
# Example: Scan distance over COM port
python python/bb84_uwoc_measure.py --port COM28 --scan distance

# Long, checkpointed data collection run
python python/fpga_collect.py --port COM28 --phase fixed     

# Compare measurement results against the model
python python/check_vs_theory.py                             
```
*Tip: `fpga_collect.py` writes one CSV row per completed point. If interrupted, an overnight run will seamlessly resume where it left off. Use `--scale 0.01` for a fast end-to-end dry run.*

---

## 🏗 System Architecture

### Adaptive Controller

The controller operates across four modes with asymmetric hysteresis to guarantee security. Signal-to-Noise Ratio (SNR) is **normalized**—where 128 represents the link's nominal click rate—factoring out the static path loss $exp(−c \cdot d)$ so the controller observes only the fading margin.

| Mode | QBER | SNR (norm.) | Jitter | $\mu$ | Basis $p_z$ | Slot | Strategy |
|---|---:|---:|---:|---:|---:|---:|---|
| **Aggressive** | < 4 % | $\ge$ 160 | < 6 | 6/15 | 50 % | 5 ms | Maximum throughput |
| **Moderate** | < 8 % | $\ge$ 96 | — | 9/15 | 60 % | 10 ms | Balanced |
| **Conservative** | < 15 % | > 40 | $\ge$ 16 | 12/15 | 80 % | 50 ms | Maximum reliability |
| **Pause** | $\ge$ 15 % | $\le$ 40 | — | — | — | — | Suspend transmission |

**Key Controller Features:**
- **Asymmetric Hysteresis:** Downgrades are immediate to prioritize security; upgrades require three consecutive "good" windows.
- **Valid Window Gating:** A window with fewer than 16 sifted detections holds the current state rather than making uninformed changes.
- **Photon Intensity Cap:** $\mu$ is capped at 12/15 to mitigate photon-number-splitting attacks in high-loss underwater environments.
- **Wavelength Hill-Climbing:** Actively probes neighboring wavelengths, accumulating clicks over multiple windows to average out shot noise before making a decision.

### UWOC Channel Emulator

A hardware realization of the physical channel $h = L \cdot h_s \cdot h_o$ integrated tightly with the detection stage.

- **Fading Sampling:** Uses ROM-based inverse CDFs (256 points per distribution).
- **Distributions Supported:** 8 scattering classes (Gamma) and 6 turbulence levels (Lognormal/Weibull).
- **Coherence Sampling:** Resampled every $2^{18}$ cycles ($\approx 5.24$ ms $\approx \tau_{coh}$), accurately reflecting the coherence time of water rather than per-qubit sampling.

---

## 📊 Key Results

*Monte-Carlo simulation parameters: $2\times10^6$ pulses per point, moderate turbulence (L3), $\lambda = 450$ nm, $\mu = 0.1$.*

A point is deemed *secure* only when the **upper bound** of the Clopper–Pearson interval on QBER remains below the 11% BB84 limit.

| Water type | Max secure range | QBER at that range | SKR | First insecure range |
|---|---:|---:|---:|---:|
| Clear ocean | **40 m** | 9.46 % [8.42, 10.58] | 61 bps | 45 m (QBER 14.10 %) |
| Coastal | **10 m** | 5.97 % [5.16, 6.85] | 813 bps | 13 m (QBER 10.11 %) |
| Harbor (turbid) | **2 m** | 8.99 % [7.99, 10.07] | 84 bps | 2.5 m (QBER 17.47 %) |

Detailed results and figures can be found in [`python/Images/report/`](python/Images/report/).

---

## 🔬 Physics Model & Design Insights

The FPGA implementation is fundamentally driven by physical phenomena specific to underwater optics. Three key findings shaped our RTL design:

1. **Massive Monitoring Windows:** With $P_{click} \sim 10^{-3}$, a standard 256-attempt window collects ~0.4 clicks on average. The monitor window must be expanded to $\sim 2^{16}$ attempts to overcome shot noise.
2. **Turbulence Variance vs. Mean QBER:** Turbulence does not significantly alter the *mean* QBER; it strictly impacts the variance. Our controller utilizes an EWMA of $|\Delta \text{QBER}|$ (`qber_jitter`) as the turbulence indicator.
3. **Dead Link Detection:** Traditional `loss_rate` metrics saturate at 255 permanently due to inherent link loss. Instead, link death is detected via zero photon counts over consecutive windows.

### The Physics Model Equations

```text
h = L · h_s · h_o     L   = D_rx² / (π·(d·tanθ_div)²) · exp(−F·c(λ)·d)   [geometry + Beer-Lambert]
                      h_s ~ Gamma(1/σ_s², σ_s²)                          [scattering fading]
                      h_o ~ Lognormal (σ² < 1) / Weibull (σ² ≥ 1)        [oceanic turbulence]

n̄       = μ · L(d) · h · η_det
P_click = 1 − (1 − Y₀)·e^(−n̄)
QBER    = [ e_pol(d)·(1 − e^(−n̄)) + ½·Y₀ ] / P_click
e_pol   = min( e₀ + k_s·(1 − e^(−b(λ)·d)), 0.5 )
```

---

## 🔌 Hardware Reference

### Hardware Platform & Configuration

| Specification | Details |
|---|---|
| **FPGA** | Altera Cyclone II **EP2C20F484C7** |
| **Board** | Terasic DE1 |
| **System Clock**| 50 MHz |
| **Host Interface**| RS-232, 115 200 baud, 8N1 |
| **Resource Usage**| 4,600 / 18,752 LEs (24.5%), Fmax = 63.74 MHz |

#### DIP Switch Configuration

| Switch | Function | Description |
|---|---|---|
| `SW[9]` | Input source | 0 = Autonomous TRNG, 1 = PC-driven via UART |
| `SW[7:5]` | Turbulence level | 000 = off ... 101 = severe |
| `SW[4]` | Channel enable | 0 = Ideal bypass, 1 = UWOC emulator active |
| `SW[3:2]` | Water type | 00 = Clear ocean, 01 = Coastal, 10 = Harbor (Latched at reset) |
| `SW[1]` | Adaptive control | 0 = Fixed parameters, 1 = Adaptive |
| `SW[0]` | Run mode | 0 = Automatic, 1 = Manual step via `KEY[1]` |
| `KEY[3]` | Reset | Resets all modules globally |
| `KEY[0]` | Eavesdropper | Hold to simulate intercept–resend attack |

> [!WARNING]
> **Data Validity Flag (`LEDG[7]`):** If this LED illuminates, the PC sent qubit commands faster than the FPGA could process them, resulting in an artificially low $P_{click}$. Reduce the `--chunk` size in your script and repeat the measurement.

### UART Protocol

**PC → FPGA (Command byte):**
- `0x01`: Reset statistics and flush FIFO.
- `0x40 | {water[1:0], lam[1:0]}`: Set water type and wavelength.
- `0x50 | turb[2:0]`: Set turbulence level.

**FPGA → PC (Data frame, one line per detected qubit):**
```text
@<a_data>,<a_basis>,<b_basis>,<bob_bit>,<basis_match>,<error>,<irradiance>,<total_hex>,<sifted_hex>,<errors_hex>*\r\n
```

### Timing Constraints

The TRNG relies on *intentional* combinational loops in its ring oscillators, which TimeQuest flags as errors. You must include `constraints/bb84_phase2.sdc` to declare these false paths before trusting any timing reports:
```tcl
set_false_path -from [get_keepers {*trng_core*ro*_chain*}]
```

---

## 📁 Repository Structure

```text
├── verilog/
│   ├── top_module.qpf / .qsf   # Quartus II project workspace
│   ├── top_module.v            # Top-level: BB84 FSM, UART, FIFO
│   ├── uwoc_channel.v          # ★ Underwater channel emulator
│   ├── uwoc_channel_rom.vh     # Generated ROM limits (Do not edit manually)
│   ├── channel_monitor.v       # ★ Real-time QBER/SNR/jitter estimator
│   ├── adaptive_controller.v   # ★ Adaptive FSM & wavelength controller
│   └── ...                     # Submodules (Alice, Bob, TRNG, OOK)
│
├── constraints/
│   └── bb84_phase2.sdc         # Timing constraints for Quartus
│
├── python/
│   ├── uwoc_channel_model.py   # ★ UWOC physics model and validation
│   ├── uwoc_lut_gen.py         # ★ FPGA ROM generator
│   ├── bb84_uwoc_measure.py    # Measurement scanning script
│   ├── fpga_collect.py         # Long-run hardware data collector
│   └── Images/report/          # Generated figures & CSVs
│
└── de1_pins.tcl                # DE1 board pin assignments
```

---

## 🤝 Contributing

Contributions are always welcome! Please follow these steps:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 🎓 Citation

Developed at Hanoi University of Science and Technology (HUST) under project **T2025-PC-068**. If you use this testbed in your research, please cite:

```bibtex
@misc{uwoc_bb84_fpga,
  title  = {Adaptive BB84 QKD over an Underwater Optical Channel: An FPGA Emulator with Closed-Loop Parameter Control},
  author = {HUST Project T2025-PC-068},
  year   = {2026}
}
```

---

## 📄 License

No formal open-source license has been granted yet. Please contact the authors before commercial reuse or redistribution. For academic and research purposes, please ensure proper citation as described above.
