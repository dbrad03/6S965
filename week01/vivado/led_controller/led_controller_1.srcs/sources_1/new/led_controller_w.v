`timescale 1ns / 1ps
`default_nettype none
module led_controller_w(
        input wire clk,
        input wire rst,
        input wire en,
        input wire go_up,
        input wire go_down,
        input wire stop,
        output wire[3:0] q
    );
    
    led_controller mpm (
        .clk(clk),
        .rst(!rst),
        .en(en),
        .go_up(go_up),
        .go_down(go_down),
        .stop(stop),
        .q(q));
endmodule

`default_nettype wire