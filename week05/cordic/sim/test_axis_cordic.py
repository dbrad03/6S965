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
from scipy.signal import lfilter

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
                while True:
                    await rising_edge
        else:
            pass

async def reset(clk, rst, cycles_held=3, polarity=1):
    rst.value = polarity
    await ClockCycles(clk, cycles_held)
    rst.value = not polarity

"""
Driver Functions Above and General
"""
sig_out_act = []
sig_out_exp = []

cordic_angles = [math.atan(2**(-i)) for i in range(16)]
CORDIC_GAIN = 0.607252935

def u16_to_s16(value: int) -> int:
    """Convert unsigned 16-bit to signed value without NumPy overflow warnings."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value

def s16_to_float(value: int) -> float:
    """Convert Q1.15 two's complement into float."""
    return float(u16_to_s16(value)) / 32768.0

def pack_normalised_vector(x: float, y: float):
    """Normalise (x,y) to unit length and pack into {y,x} Q1.15."""
    norm = float(np.hypot(x, y))
    if norm == 0.0: # guard for divide by 0
        norm = 1.0

    q15_max = (2**15 - 1) / 32768.0
    x_norm = np.clip(x / norm, -1.0, q15_max)
    y_norm = np.clip(y / norm, -1.0, q15_max)

    x_s16 = int(round(x_norm * 32768.0)) & 0xFFFF
    y_s16 = int(round(y_norm * 32768.0)) & 0xFFFF
    to_dut = (y_s16<<16) | x_s16
    return to_dut, norm

def cordic_model(val):
    """CORDIC software model for a packed 32-bit {y,x} input sample"""
    x_raw = val & 0xFFFF
    y_raw = (val >> 16) & 0xFFFF

    x = s16_to_float(x_raw)
    y = s16_to_float(y_raw)
    z = 0.0

    rotated = x < 0.0
    y_neg = y < 0.0

    if rotated:
        x = -x
        y = -y

    steps = [((x, y), z)]

    for i in range(16):
        if y >= 0:
            xn = x + (y / (2**i))
            yn = y - (x / (2**i))
            zn = z - cordic_angles[i]
        else:
            xn = x - (y / (2**i))
            yn = y + (x / (2**i))
            zn = z + cordic_angles[i]

        steps.append(((xn, yn), zn))
        x, y, z = xn, yn, zn

    angle_val = -z
    if rotated:
        angle_val += math.pi if not y_neg else -math.pi

    angle_val = (angle_val + 2 * math.pi) % (2 * math.pi)
    steps.append(((x, y), angle_val))
    sig_out_exp.append(steps)

@cocotb.test()
async def test_axis_cordic_basic(dut):
    """Basic AXI-stream CORDIC test"""
    """
    let's test 0,30,45,60,90,120,135,150,180,210,225,240,270,300,315,330,360
    """
    # ANGLES TO TRY COMPUTING
    angles = [0,30,45,60,90,120,135,150,180,210,225,240,270,300,315,330]
    vecs = [(math.cos(math.radians(deg)), math.sin(math.radians(deg))) for deg in angles]
    packed_vecs = []
    vec_norms = []
    # print(vecs)
    for vec in vecs:
        packed, norm = pack_normalised_vector(*vec)
        packed_vecs.append(packed)
        vec_norms.append(norm)
    
    # Create monitors and drivers after I multiply 
    inm = AXIS_Monitor(dut, 's00', dut.s00_axis_aclk, callback=cordic_model)
    outm = AXIS_Monitor(dut, 'm00', dut.s00_axis_aclk, callback=lambda x: sig_out_act.append(x))
    ind = M_AXIS_Driver(dut, 's00', dut.s00_axis_aclk)
    outd = S_AXIS_Driver(dut, 'm00', dut.s00_axis_aclk)
    
    # Start clock and reset
    cocotb.start_soon(Clock(dut.s00_axis_aclk, 10, units="ns").start())
    await reset(dut.s00_axis_aclk, dut.s00_axis_aresetn, 2, 0)
    
    # Feed test data
    # ind.append({'type': 'write_burst', "contents": {"data": packed_vecs}})
    # ind.append({'type':'pause','duration':2}) #end with pause
    
    for idx, data in enumerate(packed_vecs):
        ind.append({'type':"write_single","contents": {"data": data, "last": 1 if idx == len(packed_vecs) - 1 else 0}})
        ind.append({'type':'pause', "duration":random.randint(1,10)})
    ind.append({'type':'pause', "duration":2})
    for _ in range(50):
        outd.append({'type':'read', "duration":random.randint(1,10)})
        outd.append({'type':'pause', "duration":random.randint(1,10)})
    
    await ClockCycles(dut.s00_axis_aclk, 1000)  # Much longer than needed

    assert inm.transactions == outm.transactions, \
        f"Transaction count mismatch: in={inm.transactions}, out={outm.transactions}"
    
    mag_tolerance = .0001  # one LSB of Q1.15
    ang_tolerance = .001  # one LSB of Q0.16

    num_samples = min(len(sig_out_act), len(sig_out_exp), len(packed_vecs))

    for idx in range(num_samples):
        dut_word = sig_out_act[idx]
        hist = sig_out_exp[idx]
        packed_vec = packed_vecs[idx]
        x_raw = packed_vec & 0xFFFF
        y_raw = (packed_vec >> 16) & 0xFFFF
        norm = vec_norms[idx]

        (xn, yn), z = hist[-1]
        model_mag = norm * abs(xn) * CORDIC_GAIN
        model_ang = z % (2 * math.pi)

        dut_mag_code = dut_word & 0xFFFF
        dut_ang_code = (dut_word >> 16) & 0xFFFF

        dut_mag = (dut_mag_code / 32768.0) * norm
        dut_ang = (dut_ang_code / 65536.0) * 2 * math.pi
        x_int = u16_to_s16(x_raw)
        y_int = u16_to_s16(y_raw)

        dut._log.info(
            "xraw={0:+6d} yraw={1:+6d}\nmag: model={2:.6f} dut={3:.6f}\nang: model={4:.6f} dut={5:.6f}\n"
            .format(x_int, y_int, model_mag, dut_mag, model_ang, dut_ang)
        )

        assert abs(dut_mag - model_mag) <= 0.0001, \
            f"magnitude mismatch for input {idx}: model={model_mag}, dut={dut_mag}"
        assert abs((dut_ang - model_ang + math.pi) % (2 * math.pi) - math.pi) <= ang_tolerance, \
            f"angle mismatch for input {idx}: model={model_ang}, dut={dut_ang}"

    
def axis_runner():
    """Simulate the AXI-stream FIR 15 using the Python runner."""
    hdl_toplevel_lang = os.getenv("HDL_TOPLEVEL_LANG", "verilog")
    sim = os.getenv("SIM", "icarus")
    proj_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(proj_path / "sim" / "model"))
    sys.path.append(str(proj_path / "hdl"))
    
    sources = [proj_path / "hdl" / "axis_cordic.sv"]
    build_test_args = ["-Wall"]
    parameters = {}
    
    sys.path.append(str(proj_path / "sim"))
    runner = get_runner(sim)
    hdl_toplevel = "axis_cordic"
    
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
