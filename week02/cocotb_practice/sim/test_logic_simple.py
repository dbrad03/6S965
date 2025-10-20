import cocotb
import os
import random
import sys
from math import log
import logging
from pathlib import Path
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles, RisingEdge, FallingEdge
from cocotb.triggers import ReadOnly,with_timeout, Edge, ReadWrite, NextTimeStep
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
test_file = os.path.basename(__file__).replace(".py","")


@cocotb.test()
async def test_a(dut):
    """cocotb test for messing with verilog simulation"""
    dut._log.info("Starting...")
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start(start_high=False))
    dut.en.value = 0;
    dut.rst.value = 1;
    await RisingEdge(dut.clk)
    await ReadWrite()
    dut.clk.value = 0
    await Timer(5,'ns')
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    await ReadWrite()
    dut.clk.value = 0
    await RisingEdge(dut.clk)
    await ReadWrite()
    dut.clk.value = 0
    await Timer(5, 'ns')
    dut.en.value = 1
    await RisingEdge(dut.en)
    await RisingEdge(dut.clk)
    await ReadWrite()
    dut.clk.value = 0
    dut.count.value = 0
    await Timer(5, 'ns')
    dut.count.value = 10
    await Edge(dut.count)
    await Timer(5, 'ns')
    await RisingEdge(dut.clk)
    await ReadWrite()
    dut.clk.value = 0
    dut.count.value = 10
    await Timer(5, 'ns')

def test_runner():
    """Simulate the counter using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sources = [proj_path / "hdl" / "simple_logic.sv"]
    build_test_args = ["-Wall"]
    sys.path.append(str(proj_path / "sim"))
    hdl_toplevel = "simple_logic"
    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        always=True,
        build_args=build_test_args,
        parameters={},
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
    test_runner()
