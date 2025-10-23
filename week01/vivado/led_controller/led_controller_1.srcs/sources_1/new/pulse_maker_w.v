`timescale 1ns / 1ps
`default_nettype none
module pulse_maker_w(   input wire clk,
                        input wire rst,
                        output wire pulse
    ); //pure verilog does not have logics only wires.
 
    //instance of pulse maker:
    pulse_maker mpm (
        .clk(clk),
        .rst(rst),
        .pulse(pulse));
endmodule
 
`default_nettype wire