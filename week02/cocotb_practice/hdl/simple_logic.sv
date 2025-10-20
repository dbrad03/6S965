`timescale 1ns / 1ps //used for time scale specification
`default_nettype none //way to prevent net inference
 
module simple_logic(
    input wire clk,
    input wire rst,
    input wire en,
    output logic [7:0] count,
    output logic en_o
    );
    initial begin
        count <= 8'b0;
    end
    assign en_o = en;
    always_ff @(posedge clk)begin
        if(rst)begin
            count <= 8'b0;
        end else begin
            count <= count + en;
        end
    end
endmodule
 
`default_nettype wire
