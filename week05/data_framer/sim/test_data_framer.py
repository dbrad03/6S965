import cocotb
import os
import random
import sys
import math
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

test_file = os.path.basename(__file__).replace(".py", "")

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

# class AXIS_Driver(BusDriver):
#     def __init__(self, dut, name, clk, role="M"):
#         self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata', 'axis_tstrb']
#         BusDriver.__init__(self, dut, name, clk)
#         self.clock = clk
#         self.dut = dut

# class M_AXIS_Driver(AXIS_Driver):
#     def __init__(self, dut, name, clk):
#         super().__init__(dut, name, clk)
#         self.bus.axis_tdata.value = 0
#         self.bus.axis_tstrb.value = 0xF
#         self.bus.axis_tlast.value = 0
#         self.bus.axis_tvalid.value = 0

#     async def _driver_send(self, value, sync=True):
#         rising_edge = RisingEdge(self.clock)
#         falling_edge = FallingEdge(self.clock)
#         read_only = ReadOnly()
        
#         if value.get("type") == "pause":
#             await falling_edge
#             self.bus.axis_tvalid.value = 0
#             self.bus.axis_tlast.value = 0
#             for i in range(value.get("duration", 1)):
#                 await rising_edge
#         elif value.get("type") == "write_single":
#             await falling_edge
#             self.bus.axis_tvalid.value = 1
#             self.bus.axis_tlast.value = value.get("contents").get("last")
#             self.bus.axis_tdata.value = int(value.get("contents").get("data"))
#             while True:
#                 await rising_edge
#                 await read_only
#                 if self.bus.axis_tready.value:
#                     break
#             await falling_edge
#             self.bus.axis_tvalid.value = 0
#             self.bus.axis_tlast.value = 0
#             await rising_edge
#         elif value.get("type") == "write_burst":
#             data_list = value.get("contents").get("data")   
#             for i, data in enumerate(data_list):
#                 await falling_edge
#                 self.bus.axis_tdata.value = int(data)
#                 self.bus.axis_tlast.value = 1 if i == len(data_list) - 1 else 0
#                 self.bus.axis_tvalid.value = 1
#                 while True:
#                     await rising_edge
#                     await read_only
#                     if self.bus.axis_tready.value:
#                         break
#             await falling_edge
#             self.bus.axis_tvalid.value = 0
#             self.bus.axis_tlast.value = 0
#             await rising_edge
#         else:
#             pass

# class S_AXIS_Driver(BusDriver):
#     def __init__(self, dut, name, clk):
#         self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata', 'axis_tstrb']
#         BusDriver.__init__(self, dut, name, clk)
#         self.bus.axis_tready.value = 0

#     async def _driver_send(self, value, sync=True):
#         rising_edge = RisingEdge(self.clock)
#         falling_edge = FallingEdge(self.clock)
        
#         if value.get("type") == "pause":
#             await falling_edge
#             self.bus.axis_tready.value = 0
#             for i in range(value.get("duration", 1)):
#                 await rising_edge
#         elif value.get("type") == "read":
#             await falling_edge
#             self.bus.axis_tready.value = 1
#             for _ in range(value.get("duration", 1)):
#                 await rising_edge
#             await falling_edge
#             self.bus.axis_tready.value = 0
#             await rising_edge
#         else:
#             pass

"""
Monitor/Driver Functions Above and General
"""

@cocotb.test()
async def test_data_framer(dut):
    rising_edge = RisingEdge(dut.pixel_clk)
    falling_edge = FallingEdge(dut.pixel_clk)
    readonly = ReadOnly()
    burst_length = 65536
    debounce_cycles = 256

    # inm = AXIS_Monitor(dut, 's00', dut.pixel_clk)
    outm = AXIS_Monitor(dut, 'm00', dut.pixel_clk)
    # ind = M_AXIS_Driver(dut, 's00', dut.pixel_clk)
    outd = S_AXIS_Driver(dut, 'm00', dut.pixel_clk)
    
    # Start clock and reset
    cocotb.start_soon(Clock(dut.pixel_clk, 10, units="ns").start())
    await rising_edge
    await falling_edge
    dut.pixel_data.value = 0
    dut.trigger.value = 0
    dut.m00_axis_tready.value = 0
    await rising_edge
    await falling_edge
    dut.trigger.value = 1
    await ClockCycles(dut.pixel_clk, debounce_cycles+4)
    dut.trigger.value = 0
    
    for _ in range(115000):
        await falling_edge
        dut.m00_axis_tready.value = random.randint(1,5) <= 3
        dut.pixel_data = random.randint(0,2**24-1)
        await rising_edg
    
    assert 65536 == outm.transactions, \
        f"Transaction count mismatch: in={inm.transactions}, out={outm.transactions}"
    
    # assert sig_out_act == sig_out_exp, "Data mismatch between input and output stream"
    
def axis_runner():
    """Simulate the AXI-stream FIR 15 using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sys.path.append(str(proj_path / "hdl"))
    
    sources = [proj_path / "hdl" / "data_framer.sv"]
    build_test_args = ["-Wall"]
    parameters = {}
    
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    hdl_toplevel = "data_framer"
    
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
    axis_runner()
