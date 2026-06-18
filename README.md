# 6.S965 — Digital Systems II

Coursework and projects from **MIT 6.S965 (Digital Systems II)**, a hands-on RTL design course
targeting the AMD/Xilinx **Pynq-Z2 (Zynq-7020)** and **RFSoC 4x2** platforms. Each module pairs
synthesizable SystemVerilog with a [cocotb](https://www.cocotb.org/) testbench and a Vivado
block design for on-board bring-up.

> **Looking for the capstone?** The final project — a fully pipelined **GGX VNDF sampler for
> real-time ray tracing** — has its own polished repository:
> **[FPGA-GGX-Sampler](https://github.com/dbrad03/FPGA-GGX-Sampler)**. A snapshot also lives in
> [`final/`](./final) here.

## Repository layout

Each `weekNN/` folder follows the same structure:

- `hdl/` — synthesizable SystemVerilog/Verilog sources
- `sim/` — cocotb tests and Python reference models
- `vivado/` — block design, constraints, and generated bitstream for hardware bring-up

| Module | Topic | Highlights |
|--------|-------|------------|
| [`week01`](./week01) | Fundamentals | LED controller, counter, clock divider |
| [`week02`](./week02) | Serial I/O + MMIO | SPI transmitter, AXI4-Lite memory-mapped interface |
| [`week03`](./week03) | DSP + video | 15-tap FIR filter integrated into an HDMI/DVI pipeline |
| [`week04`](./week04) | Streaming + DMA | AXI4-Stream FIR, custom math IP, AXI DMA loopback |
| [`week05`](./week05) | CORDIC + framing | CORDIC core, data framer, FIR streamed over DMA |
| [`week06`](./week06) | RFSoC bring-up | AXI4-Stream skid buffer, I/Q framer on the RFSoC 4x2 |
| [`week07`](./week07) | Digital up/down conversion | CIC compiler chain on the RFSoC RF data converters |
| [`week08`](./week08) | RF capstone | ADS-B decoder — preamble detector, CORDIC, FIR demod |
| [`final`](./final) | **GGX VNDF sampler** | Pipelined ray-tracing accelerator ([standalone repo](https://github.com/dbrad03/FPGA-GGX-Sampler)) |

## Tooling

- **HDL:** SystemVerilog / Verilog
- **Verification:** cocotb + Python reference models (GTKWave / Surfer for waveforms)
- **Implementation:** AMD/Xilinx Vivado
- **Targets:** Pynq-Z2 (Zynq-7020), RFSoC 4x2 (Zynq UltraScale+)

## Notes

This is a coursework archive: the weekly modules are lab exercises that build toward the final
project, so they vary in polish. The constraint files (`base.xdc`) and Vivado block designs are
included so each design can be rebuilt and run on hardware.
