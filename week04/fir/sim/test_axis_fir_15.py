import cocotb
import os
import random
import sys
from math import log
import numpy
import logging
from pathlib import Path
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles, RisingEdge, FallingEdge, ReadOnly, with_timeout
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
from cocotb_bus.bus import Bus
from cocotb_bus.drivers import BusDriver
from cocotb_bus.monitors import BusMonitor
from cocotb_bus.scoreboard import Scoreboard
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from scipy.signal import lfilter

test_file = os.path.basename(__file__).replace(".py", "")

# FIR coefficients for testing
SMOOTH_COEFFS = [-2, -3, -4, 0, 9, 21, 32, 36, 32, 21, 9, 0, -4, -3, -2]
JUMPY_COEFFS = [-3, 14, -20, 6, 16, -5, -41, 68, -41, -5, 16, 6, -20, 14, -3]
CUSTOM_COEFFS = [-7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7]

class AXIS_Monitor(BusMonitor):
    """
    monitors axi streaming bus
    """
    transactions = 0  # use this variable to track good ready/valid handshakes
    
    def __init__(self, dut, name, clk, callback=None):
        self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata', 'axis_tstrb']
        BusMonitor.__init__(self, dut, name, clk, callback=callback)
        self.clock = clk
        self.transactions = 0
        self.dut = dut
    async def _monitor_recv(self):
        """
        Monitor receiver
        """
        rising_edge = RisingEdge(self.clock)
        falling_edge = FallingEdge(self.clock)
        read_only = ReadOnly()
        
        wait = False
        while True:
            await falling_edge
            await read_only
            valid = self.bus.axis_tvalid.value
            ready = self.bus.axis_tready.value
            last = self.bus.axis_tlast.value
            data = self.bus.axis_tdata.value

            if valid and ready:
                self.transactions += 1
                thing = dict(data=data.signed_integer, last=last,
                             name=self.name, count=self.transactions)
                self.dut._log.info(f"{self.name}: {thing}")
                self._recv(data.signed_integer)

class AXIS_Driver(BusDriver):
    def __init__(self, dut, name, clk, role="M"):
        self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata', 'axis_tstrb']
        BusDriver.__init__(self, dut, name, clk)
        self.clock = clk
        self.dut = dut

class M_AXIS_Driver(AXIS_Driver):
    def __init__(self, dut, name, clk):
        super().__init__(dut, name, clk)
        self.bus.axis_tdata.value = 0
        self.bus.axis_tstrb.value = 0xF
        self.bus.axis_tlast.value = 0
        self.bus.axis_tvalid.value = 0

    async def _driver_send(self, value, sync=True):
        rising_edge = RisingEdge(self.clock)
        falling_edge = FallingEdge(self.clock)
        read_only = ReadOnly()
        
        if value.get("type") == "pause":
            await falling_edge
            self.bus.axis_tvalid.value = 0
            self.bus.axis_tlast.value = 0
            for i in range(value.get("duration", 1)):
                await rising_edge
        elif value.get("type") == "write_single":
            await falling_edge
            self.bus.axis_tvalid.value = 1
            self.bus.axis_tlast.value = value.get("contents").get("last")
            self.bus.axis_tdata.value = int(value.get("contents").get("data"))
            while True:
                await rising_edge
                await read_only
                if self.bus.axis_tready.value:
                    break
            await falling_edge
            self.bus.axis_tvalid.value = 0
            self.bus.axis_tlast.value = 0
            await rising_edge
        elif value.get("type") == "write_burst":
            data_list = value.get("contents").get("data")
            for i, data in enumerate(data_list):
                await falling_edge
                self.bus.axis_tdata.value = int(data)
                self.bus.axis_tlast.value = 1 if i == len(data_list) - 1 else 0
                self.bus.axis_tvalid.value = 1
                while True:
                    await rising_edge
                    await read_only
                    if self.bus.axis_tready.value:
                        break
            await falling_edge
            self.bus.axis_tvalid.value = 0
            self.bus.axis_tlast.value = 0
            await rising_edge
        else:
            pass

class S_AXIS_Driver(BusDriver):
    def __init__(self, dut, name, clk):
        self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata', 'axis_tstrb']
        AXIS_Driver.__init__(self, dut, name, clk)
        self.bus.axis_tready.value = 0
    async def _driver_send(self, value, sync=True):
        rising_edge = RisingEdge(self.clock)
        falling_edge = FallingEdge(self.clock)
        
        if value.get("type") == "pause":
            await falling_edge
            self.bus.axis_tready.value = 0
            for i in range(value.get("duration", 1)):
                await rising_edge
        elif value.get("type") == "read":
            await falling_edge
            self.bus.axis_tready.value = 1
            for _ in range(value.get("duration", 1)):
                while True:
                    await rising_edge
        else:
            pass

async def reset(clk, rst, cycles_held=3, polarity=1):
    rst.value = polarity
    await ClockCycles(clk, cycles_held)
    rst.value = not polarity

def generate_signed_8bit_sine_waves(sample_rate, duration, frequencies, amplitudes):
    """
    Generate test signals for FIR testing
    """
    num_samples = int(sample_rate * duration)
    time_points = np.arange(num_samples) / sample_rate
    result = np.zeros(num_samples, dtype=int)
    
    assert len(frequencies) == len(amplitudes), "frequencies must match amplitudes"
    for i in range(len(frequencies)):
        sine_wave = amplitudes[i] * np.sin(2 * np.pi * frequencies[i] * time_points)
        scaled_wave = sine_wave * 127
        result += scaled_wave.astype(np.int8)
    
    return (time_points, result)

async def setup_coefficients(dut, coeffs):
    """Helper function to set up coefficients"""
    # coeffs_array = np.array(coeffs, dtype=np.int8)
    for a in range(15):
        for b in range(8):
            dut.coeffs[b+8*a].value = ((coeffs[a] + 256 if (coeffs[a] < 0) else coeffs[a])>>b)&0x1

def generate_waveforms(t, signals, name):
    assert len(signals)==3
    
    plt.figure(figsize=(12, 10))  # Make figure larger
    plt.suptitle("Model and DUT Comparison", fontsize=16, y=0.98)  # Move main title higher

    # First subplot: Input Signal
    plt.subplot(3, 1, 1)
    plt.plot(t, signals[0], color='gold', linewidth=2)
    plt.title('Input Signal', pad=17)  # Reduce padding for first subplot
    plt.grid(True)

    # Second subplot: Scipy If Output
    plt.subplot(3, 1, 2)
    plt.plot(t, signals[1], color='blue')
    plt.title('Scipy FIR Output', pad=20)  # Add padding to title
    plt.grid(True)

    # Third subplot: DUT Output
    plt.subplot(3, 1, 3)
    plt.plot(t, signals[2], color='green')
    plt.title('DUT Output', pad=20)  # Add padding to title
    plt.xlabel('Time (sec)')
    plt.grid(True)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])  # Leave space for main title
    plt.savefig(name, dpi=150, bbox_inches='tight')  # Save with tight bounding box
    plt.close()  # Close figure to free memory

sig_out_act = []
sig_out_exp = []
sig_out_exp_for_scoreboard = []  # Separate list for scoreboard

# Initialize filter state (14 zeros for 15-tap FIR)
zi = np.zeros(15-1)  # 15 coefficients - 1 = 14 initial conditions

def fir_model(val):
    """FIR model callback for sequential input"""
    global zi, sig_out_exp, sig_out_exp_for_scoreboard
    result, zi = lfilter(CUSTOM_COEFFS, [1.0], [val], zi=zi)
    output = int(result[0])
    sig_out_exp.append(output)
    sig_out_exp_for_scoreboard.append(output)

@cocotb.test()
async def test_axis_fir_basic(dut):
    """Basic AXI-stream FIR test without backpressure"""
    
    # Reset global state for this test
    global zi, sig_out_act, sig_out_exp, sig_out_exp_for_scoreboard
    zi = np.zeros(15-1)  # Reset filter state
    sig_out_act = []
    sig_out_exp = []
    sig_out_exp_for_scoreboard = []
    
    await setup_coefficients(dut, CUSTOM_COEFFS)
    
    # Create monitors and drivers
    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk, callback=fir_model)
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk, callback=lambda x: sig_out_act.append(x))
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    # Scoreboard with simple global variable (like j_math test)
    scoreboard = Scoreboard(dut, fail_immediately=False)
    scoreboard.add_interface(outm, sig_out_exp_for_scoreboard)
    
    # Generate test data
    t, si = generate_signed_8bit_sine_waves(
        sample_rate=100e6,
        duration=10e-6,
        frequencies=[46e6,20e6, 200e3],
        amplitudes=[0.1,0.1, 0.5]
    )
    
    # Generate expected outputs using scipy lfilter (once upfront)
    scipy_out = lfilter(CUSTOM_COEFFS, [1.0], si)
    
    # Start clock and reset
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    # Feed test data
    for sample in si:
        data = {'type': 'write_single', "contents": {"data": int(sample) & 0xFFFFFFFF, "last": 0}}
        ind.append(data)
        pause = {'type': 'pause', 'duration': random.randint(1, 6)}
        ind.append(pause)
    ind.append({'type':'pause','duration':2}) #end with pause
    # write_queue = list(filter(lambda x: x[0].get('type')=='write_single', ind._sendQ))
    
    # S-side driver with backpressure (alternating read/pause)
    for _ in range(len(si)//3):  # Create backpressure every ~10 samples
        outd.append({'type': 'read', "duration": random.randint(1, 10)})
        outd.append({'type': 'pause', "duration": random.randint(1, 10)})
    
    outd.append({'type': 'read', "duration": 1200})
    # read_queue = list(filter(lambda x: x[0].get('type')=='read', outd._sendQ))
    
    await ClockCycles(dut.s00_axis_aclk, len(si) * 1)  # Much longer than needed
    
    # FLUSH OUTPUT
    while outm.transactions < inm.transactions:
        outd.append({'type': 'read', "duration": 1})
        await RisingEdge(dut.s00_axis_aclk)
        await ReadOnly()
        
    assert inm.transactions == outm.transactions, \
        f"Transaction count mismatch: in={inm.transactions}, out={outm.transactions}"
    
    dut._log.info(f"Collected {len(sig_out_act)} actual outputs")
    dut._log.info(f"Generated {len(sig_out_exp)} expected outputs")
    dut._log.info(f"Transaction counts: in={inm.transactions}, out={outm.transactions}")
    # dut._log.info(f"Scipy produced {len(scipy_out)} outputs (batch model)")
    
    assert len(sig_out_act) > 0, "FIR filter produced no outputs!"
    assert len(sig_out_exp) > 0, "FIR filter model produced no outputs!"
    # assert len(sig_out_act) == len(sig_out_exp), f"Length mismatch: FIR={len(sig_out_act)}, scipy={len(scipy_out)}"
    
    min_len = min(len(sig_out_act),len(sig_out_exp))
    diff = np.abs(np.array(sig_out_exp[:min_len]) - np.array(sig_out_act[:min_len])) 
    assert np.all(diff <= 0), f"Outputs differ from scipy: max_diff={np.max(diff)}, tolerance={0}"
    
    # Generate plot - compare hardware with sequential model
    output_file = "axis_fir_basic_output.png"
    # generate_waveforms(t[:len(sig_out_exp)], (si[:len(sig_out_exp)], sig_out_exp, sig_out_act), output_file)
    # dut._log.info(f"Saved waveform plot to {output_file}")

@cocotb.test()
async def test_b(dut):
    global zi, sig_out_act, sig_out_exp, sig_out_exp_for_scoreboard
    zi = np.zeros(15-1)  # Reset filter state
    sig_out_act = []
    sig_out_exp = []
    sig_out_exp_for_scoreboard = []
    
    await setup_coefficients(dut, CUSTOM_COEFFS)
    
    # Create monitors and drivers
    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk, callback=fir_model)
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk, callback=lambda x: sig_out_act.append(x))
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    # Scoreboard with simple global variable (like j_math test)
    scoreboard = Scoreboard(dut, fail_immediately=False)
    scoreboard.add_interface(outm, sig_out_exp_for_scoreboard)
    
    # Generate test data
    t, si = generate_signed_8bit_sine_waves(
        sample_rate=100e6,
        duration=10e-6,
        frequencies=[46e6,20e6, 200e3],
        amplitudes=[0.1,0.1, 0.5]
    )
    
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    ind.append({"type":"write_burst", "contents": {"data": si}})
    ind.append({"type": "pause", "duration":2})
    
    for _ in range(600):
        outd.append({'type':'read', "duration":random.randint(1,10)})
        outd.append({'type':'pause', "duration":random.randint(1,10)})
    await ClockCycles(dut.s00_axis_aclk, len(si)*6)
    assert inm.transactions==outm.transactions
    assert np.all(np.abs(np.array(sig_out_exp) - np.array(sig_out_act)) <= 0)

def axis_fir_runner():
    """Simulate the AXI-stream FIR 15 using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sys.path.append(str(proj_path / "hdl"))
    
    sources = [proj_path / "hdl" / "axis_fir_15.sv"]
    build_test_args = ["-Wall"]
    parameters = {}
    
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    hdl_toplevel = "axis_fir_15"
    
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        always=True,
        build_args=build_test_args,
        parameters=parameters,
        timescale=('1ns', '1ps'),
        waves=True
    )
    
    run_test_args = []
    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module=test_file,
        test_args=run_test_args,
        waves=True
    )

if __name__ == "__main__":
    axis_fir_runner()
