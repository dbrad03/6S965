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
        BusDriver.__init__(self, dut, name, clk)
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
                await rising_edge
            await falling_edge
            self.bus.axis_tready.value = 0
            await rising_edge
        else:
            pass

async def reset(clk, rst, cycles_held=3, polarity=1):
    rst.value = polarity
    await ClockCycles(clk, cycles_held)
    rst.value = not polarity

"""
Monitor/Driver Functions Above and General
"""
EMPTY, BUSY, FULL = 0, 1, 2

def next_state_ref(cur, insert, remove):
    if cur == EMPTY:
        return BUSY if (insert and not remove) else EMPTY
    if cur == BUSY:
        if insert and remove:      return BUSY   # flow
        if insert and not remove:  return FULL   # fill
        if (not insert) and remove:return EMPTY  # unload
        return BUSY
    if cur == FULL:
        if (not insert) and remove:return BUSY   # flush
        return FULL
    return EMPTY

async def goto_state(dut, ind, outd, target):
    while True:
        await ReadOnly()
        cur = int(dut.state.value)
        if cur == target:
            # dut._log.info(f"current state: {cur}, target: {target}")
            return

        if cur == EMPTY:
            # LOAD: write one beat, don't read
            ind.append({"type":"write_single", "contents":{"data":0x1, "last":0}})
            outd.append({"type":"pause", "duration":1})
        elif cur == BUSY:
            if target == FULL:
                # FILL
                ind.append({"type":"write_single", "contents":{"data":0x2, "last":0}})
                outd.append({"type":"pause", "duration":1})
            else:
                # UNLOAD
                outd.append({"type":"read", "duration":1})
                ind.append({"type":"pause", "duration":1})
        elif cur == FULL:
            # FLUSH
            outd.append({"type":"read", "duration":1})
            ind.append({"type":"pause", "duration":1})
        await RisingEdge(dut.s00_axis_aclk)

@cocotb.test()
async def test_skid_buffer_transitions(dut):
    """Basic AXI-stream skid_buffer test"""
    rising_edge = RisingEdge(dut.s00_axis_aclk)
    falling_edge = FallingEdge(dut.s00_axis_aclk)
    readonly = ReadOnly()
    
    # Create monitors and drivers
    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk)
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk)
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    # Start clock and reset
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    combos = [(0,0), (0,1), (1,0), (1,1)]
    seq = 0

    async def idle_cycle():
        """Drive both interfaces idle for one beat so ready/valid settle."""
        ind.append({"type":"pause", "duration":1})
        outd.append({"type":"pause", "duration":1})
        await falling_edge
        await rising_edge
        await readonly
    
    for start in (EMPTY, BUSY, FULL): 
        
        for (sv, mr) in combos:
            dut._log.info(f"\n\nDRIVING TO: {"EMPTY" if not start else "BUSY" if start==1 else "FULL"}")
            await goto_state(dut, ind, outd, start) # go to starting state
            await idle_cycle()
            cur = int(dut.state.value)
            dut._log.info(f"starting state: {cur}")
            assert start == cur
            
            outd.append({"type":"read", "duration":1} if mr else {"type":"pause", "duration":1})
            ind.append({"type":"write_single", "contents":{"data":seq & 0xFFFFFFFF, "last":0}} if sv else {"type":"pause", "duration":1})  
            dut._log.info(f"Trying: s_valid={sv}, m_ready={mr}")

            await falling_edge
            await readonly

            state_sample = int(dut.state.value)
            dut._log.info(f"current state: {state_sample}")
            s_valid = int(dut.s00_axis_tvalid.value)
            s_ready = int(dut.s00_axis_tready.value)
            m_valid = int(dut.m00_axis_tvalid.value)
            m_ready = int(dut.m00_axis_tready.value)
            insert = s_valid & s_ready
            remove = m_valid & m_ready
            exp_next = next_state_ref(cur, insert, remove)
            dut._log.info(
                f"expected next state: {exp_next},  from insert={insert}, remove={remove}, "
                f"tready={m_ready}, tvalid={m_valid}"
            )

            load = int(dut.load.value)
            flow = int(dut.flow.value)
            fill = int(dut.fill.value)
            unload = int(dut.unload.value)
            flush = int(dut.flush.value)
            fired = load + flow + fill + unload + flush
            # when next state differs or equals but flow happened, exactly one op should assert
            expect_op = (exp_next != cur) or (cur == BUSY and insert and remove)
            
            if expect_op:
                # dut._log.info(f"state: {cur}, prev insert: {insert}, prev remove: {remove}")
                assert fired == 1, f"Expected exactly one op bit; got load={load},flow={flow},fill={fill},unload={unload},flush={flush}"
            else:
            #     dut._log.info(f"HOLD STATE")
                assert fired == 0, f"Expected hold (no op), but some op bit fired"

            await rising_edge
            await readonly
            next_state = int(dut.state.value)
            dut._log.info(f"actual next state: {next_state}")
            assert next_state == exp_next, \
                f"[{seq}] from {start} with (sv,mr)=({sv},{mr}) -> exp {exp_next}, act_state {next_state} (ins={insert}, rem={remove})"
            seq += 1
            await idle_cycle()
            # ind.append({"type":"pause", "duration":1})
            
    await goto_state(dut, ind, outd, EMPTY)
    await rising_edge
    await readonly
        
    ind.append({'type':'pause', "duration":2})
    outd.append({'type':'pause', "duration":2})
    assert inm.transactions == outm.transactions, \
        f"in/out transaction count mismatch. i  n transactions: {inm.transactions}, out: {outm.transactions}"    
    

@cocotb.test()
async def test_skid_buffer_latency(dut):
    rising_edge = RisingEdge(dut.s00_axis_aclk)
    falling_edge = FallingEdge(dut.s00_axis_aclk)
    readonly = ReadOnly()
    
    # Create monitors and drivers
    sig_out_exp = []
    sig_out_act = []
    in_cycles = []
    out_cycles = []
    clk_period = 10  # ns, matches Clock configuration

    def make_cb(store, cycle_store):
        def _cb(value):
            store.append(value)
            cycle_store.append(int(gst(units="ns") // clk_period))
        return _cb

    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk, callback=make_cb(sig_out_exp, in_cycles))
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk, callback=make_cb(sig_out_act, out_cycles))
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    # Start clock and reset
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    data = list(range(50))
    
    ind.append({"type": "write_burst", "contents": {"data": data}})
    ind.append({"type": "pause", "duration": 2})
    outd.append({"type": "read", "duration": len(data) + 5})

    await ClockCycles(dut.s00_axis_aclk, 100)
    await readonly
    # while outm.transactions < len(data):
    #     await rising_edge
    #     await readonly
    
    assert inm.transactions == outm.transactions, \
        f"Transaction count mismatch: in={inm.transactions}, out={outm.transactions}"
    
    assert sig_out_act == sig_out_exp, "Data mismatch between input and output stream"

    latencies = [out_cycles[i] - in_cycles[i] for i in range(len(data))]
    assert all(lat in (0, 1) for lat in latencies), f"Unexpected latency values: {latencies}"

@cocotb.test()
async def test_skid_buffer_backpressure(dut):
    rising_edge = RisingEdge(dut.s00_axis_aclk)
    falling_edge = FallingEdge(dut.s00_axis_aclk)
    readonly = ReadOnly()
    
    
    sig_out_exp = []
    sig_out_act = []
    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk, callback=lambda x: sig_out_exp.append(x))
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk, callback=lambda x: sig_out_act.append(x))
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    for data in range(0,50):
        data = {'type': 'write_single', "contents": {"data": data & 0xFFFFFFFF, "last": 0}}
        ind.append(data)
        pause = {'type': 'pause', 'duration': random.randint(1, 6)}
        ind.append(pause)
    ind.append({'type': 'write_single', "contents": {"data": 50 & 0xFFFFFFFF, "last": 1}})
    ind.append(pause)
    
    for _ in range(50//2):  # Create backpressure every ~10 samples
        outd.append({'type': 'read', "duration": random.randint(1, 10)})
        outd.append({'type': 'pause', "duration": random.randint(1, 10)})
        
    while outm.transactions < 51:
        outd.append({'type': 'read', "duration": 1})
        await rising_edge
        await readonly
    
    assert inm.transactions == outm.transactions or inm.transactions-outm.transactions==1, \
        f"Transaction count mismatch: in={inm.transactions}, out={outm.transactions}"
    
def axis_runner():
    """Simulate the AXI-stream FIR 15 using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sys.path.append(str(proj_path / "hdl"))
    
    sources = [proj_path / "hdl" / "axis_skid_buffer.sv"]
    build_test_args = ["-Wall"]
    parameters = {}
    
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    hdl_toplevel = "axis_skid_buffer"
    
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
