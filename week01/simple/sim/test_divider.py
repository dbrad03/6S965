import cocotb
import os
import sys
import random
import logging
import numpy as np
from pathlib import Path
from generate_clock import generate_clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, ClockCycles, ReadOnly
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner

test_file = os.path.basename(__file__).replace(".py","")

def divider_model(dividend:int, divisor:int):
    x = np.uint32(dividend)
    y = np.uint32(divisor)
    return dict(quotient=x//y, remainder=x%y)

@cocotb.test()
async def first_test(dut):
    await cocotb.start( generate_clock( dut.clk_in ) )
    await FallingEdge(dut.clk_in)
    dut.rst_in.value = 1
    await ClockCycles(dut.clk_in,num_cycles=1)
    await FallingEdge(dut.clk_in)
    dut.rst_in.value = 0

    for _ in range(100):
        #...inside a larger looping test where dividend and divisor are being fed
        #set values for dividend and divisor
        
        await FallingEdge(dut.clk_in)
        dividend = random.randint(0,2**32-1)
        divisor = random.randint(0,2**32-1)
        
        expected = divider_model(dividend, divisor)
        dut.dividend_in.value = dividend
        dut.divisor_in.value = divisor
        dut.data_valid_in.value = 1
       
        # some stuff to figure out....wait.....(your job)
        while(1):
            await RisingEdge(dut.clk_in)
            await ReadOnly()
            if dut.data_valid_out.value == 1:
                eq = expected['quotient']
                er = expected['remainder']
                aq = dut.quotient_out.value.integer
                ar = dut.remainder_out.value.integer
                assert eq==aq and er==ar, f"Error! at Input: {dividend},{divisor}. Expected: {eq}, {er}. Actual {aq}, {ar}"
                dut._log.info(f"Input: {dividend},{divisor}. Expected: {eq}, {er}. Actual {aq}, {ar}")
                break
        # continue with test

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
    sources = [proj_path / "hdl" / "divider.sv"] #grow/modify this as needed. CHANGE THIS
    hdl_toplevel = "divider" # CHANGE THIS CHANGE THIS
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
