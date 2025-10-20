import cocotb
import os
import sys
import random
import logging
from pathlib import Path
from generate_clock import generate_clock
from cocotb.triggers import Timer, RisingEdge, FallingEdge, ClockCycles, ReadOnly
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
from cocotb.clock import Clock

from ref_led_design import state_t, ref_design

test_file = os.path.basename(__file__).replace(".py","")

@cocotb.test()
async def random_walk_test(dut):
    """ Try to randomly walk through state space of led_controller """
    dut._log.info("--->randomly walking")
    rising_clk_edge = RisingEdge(dut.clk)
    falling_clk_edge = FallingEdge(dut.clk)
    read_only = ReadOnly()
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start(start_high=False))
    await Timer(200, "ns")
    await falling_clk_edge
    dut.stop.value = 0
    dut.go_down.value = 0
    dut.en.value = 0
    dut.rst.value = 1
    await falling_clk_edge
    dut.rst.value = 0
    await Timer(200, "ns")
    dut.go_up.value = 1
    await falling_clk_edge
    dut.go_up.value = 1
    await falling_clk_edge
    dut.en.value = 1
    await rising_clk_edge
    await read_only
    #initial values as they are...
    en = dut.en.value
    rst = dut.rst.value
    stop = dut.stop.value
    go_up = dut.go_up.value
    go_down = dut.go_down.value
    state = state_t(dut.state.value)
    q = dut.q.value.integer

    # YOU DO: figure out what they should be after upcoming next edge:
    nstate, qout = ref_design(state,q,rst,en,stop,go_up,go_down)

    for i in range(5000):
        await rising_clk_edge
        await read_only
 
        #YOU DO: analyze outputs of dut. Compare to values you predicted... 
        dut._log.info(f"predicted state: {nstate}\npredicted q value: {qout}\n")
        dut._log.info(f"actual current vals:\nstate: {state_t(dut.state.value)}\nen: {dut.en.value}\nrst: {dut.rst.value}\nstop: {dut.stop.value}\ngo_up: {dut.go_up.value}\ngo_down: {dut.go_down.value}\nq: {dut.q.value.integer}")
        assert nstate == state_t(dut.state.value)
        assert qout == dut.q.value.integer
        state = state_t(dut.state.value)
        await falling_clk_edge
        #YOU DO:
        #   * make signals for upcoming application...
        #   * make prediction about what state/output should be after next rising edge
        #   * apply those signals to dut
        en = random.randint(0,1)
        rst = random.randint(0,1)
        stop = random.randint(0,1)
        go_up = random.randint(0,1)
        go_down = random.randint(0,1)

        dut._log.info(f"previous state: {state}\nprevious q value: {qout}")
        nstate, qout = ref_design(state,qout,rst,en,stop,go_up,go_down)
        
        dut.en.value = en
        dut.rst.value = rst
        dut.stop.value = stop
        dut.go_up.value = go_up
        dut.go_down.value = go_down

"""the code below should largely remain unchanged in structure, though the specific files and things
specified should get updated for different simulations.
"""
def sv_runner():
    """Simulate the counter using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sources = [proj_path / "hdl" / "led_controller.sv"] #grow/modify this as needed. CHANGE THIS
    hdl_toplevel = "led_controller" # CHANGE THIS CHANGE THIS
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
