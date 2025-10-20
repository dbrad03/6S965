import cocotb
import os
import sys
import random
from math import log
import logging
#import numpy as np
from pathlib import Path
from cocotb.clock import Clock
from cocotb.triggers import First, Timer, RisingEdge, FallingEdge, ClockCycles
from cocotb.triggers import ReadOnly, with_timeout, Edge, ReadWrite, NextTimeStep
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner

test_file = os.path.basename(__file__).replace(".py","")


def binary_list_to_int(message):
    val = 0
    for bit in message:
        val = (val<<1) | bit
    return val

async def drive_data_in(dut, value):
    """ Sends data in on a rising edge when busy is low """
    while True:
        await RisingEdge(dut.clk)
        await ReadOnly()
        if dut.busy.value == 0:
            break
    await FallingEdge(dut.clk)
    dut.trigger.value = 1
    dut.data_in.value = value
    await ClockCycles(dut.clk,1)
    # May have to try
    # await RisingEdge(dut.clk)
    # await FallingEdge(dut.clk)
    dut.trigger.value = 0

async def reset(clk_wire,rst_wire):
    """ Drives Reset """
    rst_wire.value = 1
    await ClockCycles(clk_wire,2)
    rst_wire.value = 0

async def model_spi_device(dut, received_messages):
    while True:
        message = []
        await FallingEdge(dut.cs) # signals start of transmission
        while True:
            await First(RisingEdge(dut.cs), RisingEdge(dut.dclk))
            await ReadOnly()
            #dut._log.info(f"cs: {dut.cs.value}, dclk: {dut.dclk.value}")
            #dut._log.info(f"copi: {dut.copi.value}\n")
            if not dut.cs.value:
                message.append(dut.copi.value)
            else:
                assert len(message)==dut.DATA_WIDTH.value
                received_messages.append(message)
                break

async def assert_spi_clock(dut):
    dclk_period = dut.DATA_CLK_PERIOD.value
    while True:
        count = 0
        last_dclk = 1
        await FallingEdge(dut.cs)
        await RisingEdge(dut.dclk)
        await ReadOnly()
        #dut._log.info(f"Sim time at cs fall: {gst('ns')} ns")
        while True:
            await RisingEdge(dut.clk)
            await ReadOnly()
            #dut._log.info(f"last dclk: {last_dclk}; curr dclk: {dut.dclk.value}")
            count += 1
            if not last_dclk and dut.dclk.value:
                #dut._log.info(f"Counted Period: {count}\n Expected period: {dclk_period}")
                if not dut.rst.value: 
                    assert count == dclk_period
                count = 0
            last_dclk = dut.dclk.value
            if dut.cs.value:
                break

async def check_message(dut, message):
    await drive_data_in(dut, message)
    await ReadOnly()
    #dut._log.info(f"Data driven in: {dut.data_in.value}")
    #dut._log.info(f"BUSY: {dut.busy.value}.. transmission started")
    await FallingEdge(dut.busy)
    #dut._log.info(f"BUSY: {dut.busy.value}.. tranmission complete")
    await ClockCycles(dut.clk,1)
    await ReadOnly()

@cocotb.test()
async def send_one_message(dut):
    message = 0xAB
    received_messages = []

    cocotb.start_soon( Clock(dut.clk, 10, units='ns').start(start_high=False ) )
    #dut.DATA_WIDTH = 
    #dut.DATA_CLK_PERIOD = 
    await reset(dut.clk,dut.rst)
    
    cocotb.start_soon( model_spi_device(dut,received_messages) )
    cocotb.start_soon( assert_spi_clock(dut) )
    await drive_data_in(dut, message)
    await ReadOnly()
    #dut._log.info(f"Data driven in: {dut.data_in.value}")
    #dut._log.info(f"BUSY: {dut.busy.value}.. transmission started")
    await FallingEdge(dut.busy)
    #dut._log.info(f"BUSY: {dut.busy.value}.. transmission complete")
    await ClockCycles(dut.clk, 1)
    await ReadOnly()
    #assert int(message)==int(''.join(str(bit) for bit in received_messages[0]),2)
    assert message == binary_list_to_int(received_messages[0])
    dut._log.info(f"Message sent: {hex(message)}\nMessage received: {hex(binary_list_to_int(received_messages[0]))}")
   

@cocotb.test()
async def send_many_messages(dut):
    messages = [random.randint(0,0xFF) for _ in range(500)]
    received_messages = []
    cocotb.start_soon( Clock(dut.clk, 10, units='ns').start(start_high=False)  )
    await reset(dut.clk,dut.rst)
    cocotb.start_soon( model_spi_device(dut, received_messages) )
    cocotb.start_soon( assert_spi_clock(dut) )
    for i, message in enumerate(messages):
        #dut._log.info(f"message to be driven in: {hex(message)}")
        await check_message(dut,message)
        assert message == binary_list_to_int(received_messages[i])
        dut._log.info(f"Message sent: {hex(message)}\nMessage received: {received_messages[i]}\n")

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
    sources = [proj_path / "hdl" / "spi_tx.sv"] #grow/modify this as needed. CHANGE THIS
    hdl_toplevel = "spi_tx" # CHANGE THIS CHANGE THIS
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
