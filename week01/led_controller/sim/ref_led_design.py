from enum import IntEnum
# Define a Python enum that mirrors the SystemVerilog enum
class state_t(IntEnum):
    STOP = 0
    SCROLL_UP = 1
    SCROLL_DOWN = 2
 
def ref_design(state,q,rst,en,stop,go_up,go_down):
    """returns tuple of (next state and output value q)"""
    if rst:
        return (state_t.STOP, 0b0001)
    else:
        new_q = q
        if en:
            if state == state_t.SCROLL_UP:
                new_q = (new_q&0x7)<<1 | ((new_q&0x8)>>3)
            elif state == state_t.SCROLL_DOWN:
                new_q = (new_q&0xE)>>1 | ((new_q&0x1)<<3)
        new_state = state
        if stop==1:
            new_state = state_t.STOP
        elif go_up==1:
            new_state = state_t.SCROLL_UP
        elif go_down==1:
            new_state = state_t.SCROLL_DOWN
        return (new_state, new_q)
