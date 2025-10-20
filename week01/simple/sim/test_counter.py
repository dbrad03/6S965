import cocotb
import os
import random
import sys
import logging
from pathlib import Path
from generate_clock import generate_clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, ClockCycles, ReadOnly
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
 
#cheap way to get the name of current file for runner:
test_file = os.path.basename(__file__).replace(".py","")
 
@cocotb.test()
async def first_test(dut):
    """ First cocotb test?
        Clock should start low then goes high __--
    """
    
    # Generate clock
    await cocotb.start( generate_clock( dut.clk ) ) #launches clock
    
    # Check initialization values
    dut._log.info(f"checking initialization values @ {gst('ns')} \
        \nclk: {dut.clk.value}\nrst: {dut.rst.value}\ncount: {dut.count.value}\nperiod: {dut.period.value}")
    
    # Set reset high for at least one cycle
    # assert count is 0
    dut.rst.value = 1
    await ReadOnly()
    assert dut.rst.value==1
    await ClockCycles(dut.clk,num_cycles=1)
    await ReadOnly()
    assert dut.count.value==0
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    dut.period.value = 0
    await ReadOnly()
    assert dut.period.value==0
    for i in range(3):
        await ClockCycles(dut.clk,num_cycles=1)
        await ReadOnly()
        assert dut.count.value==0
    await RisingEdge(dut.clk)
    dut.period.value = 15
    await ClockCycles(dut.clk,num_cycles=7)
    dut._log.info(f"checking count @ {gst('ns')}.. count: {dut.clk.value}")
    dut.rst.value=1
    await ClockCycles(dut.clk,num_cycles=1)
    await ReadOnly()
    assert dut.count.value==0
    for i in range(20):
        await ClockCycles(dut.clk,num_cycles=1)
        await ReadOnly()
        assert dut.count.value==0
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await ClockCycles(dut.clk,num_cycles=1)
    await ReadOnly()
    dut._log.info(f"count @ {gst('ns')}.. {dut.count.value}")
    assert dut.count.value==1
    await ClockCycles(dut.clk,num_cycles=14)
    await ReadOnly()
    assert dut.count.value==0
    # maybe wait one more
    for _ in range(10):
        await ClockCycles(dut.clk,num_cycles=6)
        await ReadOnly()
        dut._log.info(f"checking count @ {gst('ns')}.. count: {dut.count.value}")
    await RisingEdge(dut.clk)
    dut.period.value = 1000
    await ClockCycles(dut.clk,num_cycles=300)
    await ReadOnly()
    assert int(dut.count.value) > 16
    await ClockCycles(dut.clk,num_cycles=1000)
    await ReadOnly()
    assert int(dut.count.value) < 999
    await Timer(1000,'ns')

"""the code below should largely remain unchanged in structure, though the specific files and things
specified should get updated for different simulations.
"""
def counter_runner():
    """Simulate the counter using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sources = [proj_path / "hdl" / "counter.sv"] #grow/modify this as needed.
    hdl_toplevel = "counter"
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
    counter_runner()
