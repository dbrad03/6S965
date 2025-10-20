`timescale 1ns / 1ps


module tristate(input wire i, input wire t, inout wire oi, output wire o);

    OBUFT mob (.I(i), .T(t), .O(oi));
    IBUF mib (.I(oi), .O(o));
endmodule
