#!/usr/bin/env python3

import cocotb
import lowpass
import os
import random
import sys
from math import log
import numpy
import logging
from pathlib import Path
from cocotb.clock import Clock
from cocotb.triggers import Timer, ClockCycles, RisingEdge, FallingEdge, ReadOnly,with_timeout
from cocotb.utils import get_sim_time as gst
from cocotb.runner import get_runner
#from vicoco.vivado_runner import get_runner
#new!!!
from cocotb_bus.bus import Bus
from cocotb_bus.drivers import BusDriver
from cocotb_bus.monitors import Monitor
from cocotb_bus.monitors import BusMonitor
from cocotb_bus.scoreboard import Scoreboard
import numpy as np
test_file = os.path.basename(__file__).replace(".py","")

proj_path = Path(__file__).resolve().parent.parent

class AXISMonitor(BusMonitor):
    """
    monitors axi streaming bus
    """
    transactions = 0 #use this variable to track good ready/valid handshakes
    def __init__(self, dut, name, clk, callback=None):
        self._signals = ['axis_tvalid','axis_tready','axis_tlast','axis_tdata','axis_tstrb']
        BusMonitor.__init__(self, dut, name, clk, callback=callback)
        self.clock = clk
        self.transactions = 0
    async def _monitor_recv(self):
        """
        Monitor receiver
        """
        rising_edge = RisingEdge(self.clock) # make these coroutines once and reuse
        falling_edge = FallingEdge(self.clock)
        read_only = ReadOnly() #This is
        while True:
            await rising_edge
            await falling_edge #sometimes see in AXI shit
            await read_only  #readonly (the postline)
            valid = self.bus.axis_tvalid.value
            ready = self.bus.axis_tready.value
            last = self.bus.axis_tlast.value
            data = self.bus.axis_tdata.value #.signed_integer
            if valid and ready:
                self.transactions+=1
                thing = dict(data=data.signed_integer,last=last,name=self.name,count=self.transactions,time=gst())
                #print(f"{self.name}: {thing}")
                self._recv(data)

class AXISDriver(BusDriver):
    def __init__(self, dut, name, clk, role="M"):
        self._signals = ['axis_tvalid', 'axis_tready', 'axis_tlast', 'axis_tdata','axis_tstrb']
        BusDriver.__init__(self, dut, name, clk)
        self.clock = clk
        if role=='M':
            self.role = role
            self.bus.axis_tdata.value = 0
            self.bus.axis_tstrb.value = 0
            self.bus.axis_tlast.value = 0
            self.bus.axis_tvalid.value = 0
        elif role == 'S':
            self.role = role
            self.bus.axis_tready.value = 0
        else:
            raise ValueError("role can only be 'M' or 'S'")

    async def _driver_send(self, value, sync=True):
        rising_edge = RisingEdge(self.clock) # make these coroutines once and reuse
        falling_edge = FallingEdge(self.clock)
        read_only = ReadOnly() #This is
        if self.role == 'M':
            if value.get("type") == "write_single":
                await falling_edge #wait until after a rising edge has passed.
                self.bus.axis_tdata.value = value.get('contents').get('data')
                self.bus.axis_tstrb.value = 0xF
                self.bus.axis_tlast.value = value.get('contents').get('last')
                self.bus.axis_tvalid.value = 1 #set valid to be 1
                await read_only
                if self.bus.axis_tready.value == 0: #ifnot there...
                    await RisingEdge(self.bus.axis_tready) #wait until it does go high
                await rising_edge
                #self.bus.axis_tvalid.value = 0 #set to 0 and be done.
            elif value.get("type") == "pause":
                await falling_edge
                self.bus.axis_tvalid.value = 0 #set to 0 and be done.
                await ClockCycles(self.clock,value.get("duration",1))
            elif value.get("type") == "write_burst":
                data = value.get("contents").get("data")
                for i in range(len(data)):
                    await falling_edge
                    self.bus.axis_tdata.value = int(data[i])
                    if i == len(data)-1:
                        self.bus.axis_tlast.value = 1
                    else:
                        self.bus.axis_tlast.value = 0
                    self.bus.axis_tvalid.value = 1
                    if self.bus.axis_tready.value == 0:
                        await RisingEdge(self.bus.axis_tready)
                    await rising_edge
                #self.bus.axis_tvalid.value = 0
                #self.bus.axis_tlast.value = 0
            else:
                pass
        elif self.role == 'S':
            if value.get("type") == "pause":
                await falling_edge
                self.bus.axis_tready.value = 0 #set to 0 and be done.
                await ClockCycles(self.clock,value.get("duration",1))
            elif value.get("type") == "read_single":
                await falling_edge #wait until after a rising edge has passed.
                self.bus.axis_tready.value = 1 #set valid to be 1
                await read_only
                if self.bus.axis_tvalid.value == 0: #ifnot there...
                    await RisingEdge(self.bus.axis_tvalid) #wait until it does go high
                await rising_edge
                self.bus.axis_tready.value = 0 #set to 0 and be done.
            elif value.get("type") == "read_burst":
                for i in range(value.get("duration",1)):
                    await falling_edge #wait until after a rising edge has passed.
                    self.bus.axis_tready.value = 1 #set valid to be 1
                    await read_only
                    if self.bus.axis_tvalid.value == 0: #ifnot there...
                        await RisingEdge(self.bus.axis_tvalid) #wait until it does go high
                    await rising_edge
                self.bus.axis_tready.value = 0 #set to 0 and be done.

async def reset(clk,rst, cycles_held = 3,polarity=1):
    rst.value = polarity
    await ClockCycles(clk, cycles_held)
    rst.value = not polarity

'''
{"type":"write_single", "contents": {"data":5, "last":0}}
{"type":"pause","duration":10}
{"type":"write_burst", "contents": {"data": np.array(9*[0]+[1]+30*[0]+[-2]+59*[0])}}
{"type":"read_single"}
{"type":"read_burst", "duration":10}
'''

@cocotb.test()
async def test_a(dut):
    """cocotb test for AXIS FIR15"""
    received_squitters = []

    inm = AXISMonitor(dut,'s00',dut.s00_axis_aclk)
    outm = AXISMonitor(dut,'m00',dut.s00_axis_aclk, callback = lambda x: received_squitters.append(x.integer))
    ind = AXISDriver(dut,'s00',dut.s00_axis_aclk,"M") #M driver for S port
    outd = AXISDriver(dut,'m00',dut.s00_axis_aclk,"S") #S driver for M port
   
    # Load coefficients (ADS-B preamble)
    SAMPLE_RATE = 64e6
    SAMPLE_PERIOD = 1 / SAMPLE_RATE

    preamble_length = int(8e-6 / SAMPLE_PERIOD) # Preamble is 8 microseconds long
    preamble = []
    preamble += [1] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [0] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [1] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [0] * int(2e-6 / SAMPLE_PERIOD)
    preamble += [1] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [0] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [1] * int(0.5e-6 / SAMPLE_PERIOD)
    preamble += [0] * int(3e-6 / SAMPLE_PERIOD)

    assert len(preamble) == preamble_length, "Preamble generation failed"

    preamble_coeffs_packed = 0
    for i in range(preamble_length):
        preamble_coeffs_packed |= (preamble[i] & 0xFF) << (i * 8)
    print("Preamble coeffs packed:")
    print(hex(preamble_coeffs_packed))
    dut.preamble_coeffs.value = preamble_coeffs_packed

    lowpass_coeffs_packed = 0
    for i in range(len(lowpass.lowpass_coeffs)):
        lowpass_coeffs_packed |= (lowpass.lowpass_coeffs[i] & 0xFF) << (i * 8)
    print("Lowpass coeffs packed:")
    print(hex(lowpass_coeffs_packed))
    dut.lowpass_coeffs.value = lowpass_coeffs_packed

    dut.preamble_detector_threshold.value = 8000
    dut.decoder_threshold.value = 40

    #cocotb.start_soon(Clock(dut.s00_axis_aclk, 15625, units="ps").start()) # 64 MHz clock
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 15626, units="ps").start()) # 64 MHz clock, plus 1 ps so that /2 is even for simulator issues
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn,2,0)

    # Load example ADC data.
    #adc_data_iq = np.load(proj_path / "sim" / "adsb_squitter_64MSPS_iq.np")
    adc_data_iq = np.load(proj_path / "sim" / "adsb_squitters_fake_50dbm_64MSPS_iq.np")
    #adc_data_iq = np.load(proj_path / "sim" / "adsb_squitters_fake_40dbm_64MSPS_iq_again.np")
    real_data = adc_data_iq.real.astype(np.int16)
    imag_data = adc_data_iq.imag.astype(np.int16)
    packed_data = np.zeros((len(real_data),), dtype = np.uint32)
    for i in range(len(real_data)):
        packed_data[i] = (real_data[i].astype(np.int32) << 16) | (imag_data[i].astype(np.uint32) & 0xFFFF)

    # Write the example ADC data.
    data = {'type':'write_burst', "contents": {"data": packed_data}}
    ind.append(data)
    pause = {"type": "pause","duration": 1}
    ind.append(pause)

    # Read the processed data.
    data = {'type':'read_burst', "duration": 3}
    outd.append(data)
    outd.append(pause)

    await ClockCycles(dut.s00_axis_aclk, len(adc_data_iq) + len(preamble) + 100)

    print("Received squitters:")
    print(received_squitters)
    assert [0x8d780976990c83ad98041dc0fbd7, 0x8d780976990c83ad98041dc0fbd7] == received_squitters

def adsb_runner():
    """Simulate the ADSB decoder using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    #sim = os.getenv("SIM", "vivado")
    sys.path.append(str(proj_path / "sim" / "model"))
    sys.path.append(str(proj_path / "hdl" ))
    sources = [proj_path / "hdl" / "axis_fir.sv", proj_path / "hdl" / "preamble_detector.sv", proj_path / "hdl" / "top.sv", proj_path / "hdl" / "adsb_decoder.sv", proj_path / "hdl" / "cordic.sv"]
    #sources = [proj_path / "hdl" / "j_math.sv"]
    build_test_args = ["-Wall"]
    parameters = {} #!!!
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    hdl_toplevel = "top"
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        always=True,
        build_args=build_test_args,
        parameters=parameters,
        timescale = ('1ps','1fs'),
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
    adsb_runner()
