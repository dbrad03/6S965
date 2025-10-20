import cocotb
import os
import random
import sys
from math import log
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles, RisingEdge, FallingEdge, First
from cocotb.triggers import ReadOnly, with_timeout, Edge, ReadWrite, NextTimeStep
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
test_file = os.path.basename(__file__).replace(".py","")
from scipy.signal import lfilter

def generate_signed_8bit_sine_waves(sample_rate, duration,frequencies, amplitudes):
    """
    frequencies (float): The frequency of the sine waves in Hz.
    relative amplitudes (float) of the sinewaves (0 to 1.0).
    sample_rate (int): The number of samples per second.
    duration (float): The duration of the time series in seconds.
    """
    num_samples = int(sample_rate * duration)
    time_points = np.arange(num_samples) / sample_rate
    # Generate a sine wave with amplitude 1.0
    result = np.zeros(num_samples, dtype=int)
    assert len(frequencies) == len(amplitudes), "frequencies must match amplitudes"
    for i in range(len(frequencies)):
        sine_wave = amplitudes[i]*np.sin(2 * np.pi * frequencies[i] * time_points)
        # Scale the sine wave to the 8-bit signed range [-128, 127]
        scaled_wave = sine_wave * 127
        # make 8bit signed integers:
        result+=scaled_wave.astype(np.int8)
    return (time_points,result)

def convert_to_signed_32bit(unsigned_val):
    """Convert unsigned 32-bit value to signed 32-bit"""
    return unsigned_val - 2**32 if unsigned_val >= 2**31 else unsigned_val

def plot_waveforms(t, signals, name):
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

async def reset(clk_wire,rst_wire):
    """ Drives Reset """
    rst_wire.value = 1
    await ClockCycles(clk_wire,2)
    rst_wire.value = 0
   
async def drive_data_in(dut, value):
    await FallingEdge(dut.clk)
    dut.data_in_valid.value = 1
    # Convert 8-bit signed to 32-bit signed
    dut.data_in.value = int(value) & 0xFFFFFFFF
    await RisingEdge(dut.clk)
    dut.data_in_valid.value = 0

async def gather_output(dut, output):
    """Collect outputs until data_out_valid goes low and stays low for a few cycles"""
    valid_count = 0
    while valid_count < 5:  # Stop after 5 consecutive cycles with no valid output
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.data_out_valid.value == 1:
            # Extract the actual integer value from the cocotb signal
            output_val = int(dut.data_out.value)
            output.append(output_val)
            valid_count = 0  # Reset counter when we get valid data
        else:
            valid_count += 1
    
    dut._log.info(f"Stopped collecting outputs after {valid_count} consecutive cycles with no valid output")
    
@cocotb.test()
async def test_filter(dut):
    rising_edge = RisingEdge(dut.clk)
    falling_edge = FallingEdge(dut.clk)
    
    # coeffs
    coeffs = []
    smooth=[-2,-3,-4,0,9,21,32,36,32,21,9,0,-4,-3,-2]
    jumpy=[-3,14,-20,6,16,-5,-41,68,-41,-5,16,6,-20,14,-3]
    custom = [-7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7]
    
    coeffs.append(smooth)
    coeffs.append(jumpy)
    coeffs.append(custom)
    
    #time and signal input:
    t,si = generate_signed_8bit_sine_waves(
        sample_rate=100e6,
        duration=10e-6,
        frequencies=[46e6,20e6, 200e3],
        amplitudes=[0.1,0.1, 0.5]
    )
    cocotb.start_soon( Clock(dut.clk, 10, units='ns').start(start_high=False) )

    for i, coeff_set in enumerate(coeffs):
        # For transposed direct form FIR, we need to reverse the coefficients
        # to match the phase response of the hardware implementation
        reversed_coeffs = coeff_set[::-1]
        scipy_output = lfilter(coeff_set, [1.0], si)
        verilog_output = []
        
        await reset(dut.clk,dut.rst)
        await rising_edge
        await falling_edge
        
        for a in range(15):
            for b in range(8):
                dut.coeffs[b+8*a].value = ((coeff_set[a] + 256 if (coeff_set[a] < 0) else coeff_set[a])>>b)&0x1
        
        cocotb.start_soon( gather_output(dut,verilog_output) )
         
        for inp in si:
            await drive_data_in(dut, inp)
        
        # Add some extra cycles to ensure all outputs are collected
        await ClockCycles(dut.clk, 4)
        
        output_file = f"output_plot_{i}.png"
        fir_output = verilog_output[:]
        
        dut._log.info(f"Collected {len(fir_output)} outputs from FIR filter")
        dut._log.info(f"Expected approximately {len(si)} outputs")
        
        # Convert unsigned 32-bit values to signed 32-bit for proper comparison
        fir_output_signed = np.array(fir_output, dtype=np.uint32).astype(np.int32)
        
        # Assertions to verify FIR filter correctness
        assert len(fir_output_signed) > 0, "FIR filter produced no outputs!"
        assert len(fir_output_signed) == len(scipy_output), f"Length mismatch: FIR={len(fir_output_signed)}, scipy={len(scipy_output)}"
        
        # Compare with scipy reference (allow for some tolerance due to fixed-point arithmetic)
        tolerance = 0  # Adjust this based on your precision requirements
        
        # Use numpy to compute differences and check all at once
        diffs = np.abs(scipy_output - fir_output_signed)
        assert np.all(diffs <= tolerance), f"Outputs differ from scipy: max_diff={np.max(diffs)}, tolerance={tolerance}"

        # Use signed values for plotting
        fir_output = list(fir_output_signed)
        
        plot_waveforms(t, (si,scipy_output,fir_output), output_file)
        dut._log.info(f"Saved waveform to {output_file}" )


"""
the code below should largely remain unchanged in structure, though the specific files and things
specified should get updated for different simulations.
"""
def sv_runner():
    """Simulate the counter using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sources = [proj_path / "hdl" / "fir_15.sv"] #grow/modify this as needed. CHANGE THIS
    hdl_toplevel = "fir_15" # CHANGE THIS CHANGE THIS
    build_test_args = ["-Wall"]#,"COCOTB_RESOLVE_X=ZEROS"]
    parameters = {}
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        always=True,
        build_args=build_test_args,
        parameters=parameters,
        timescale = ('1ns','1ps'),
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
    sv_runner()
