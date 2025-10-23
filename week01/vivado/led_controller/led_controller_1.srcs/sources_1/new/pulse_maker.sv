`timescale 1ns / 1ps
`default_nettype none
//will fire a pulse once every 20 million clock cycles
//feel free to change/modify
module pulse_maker( input wire clk,
                    input wire rst,
                    output logic pulse
    );
 
    logic[31:0] counter;
    localparam PERIOD = 20_000_000;
    always_ff @(posedge clk) begin
        if(!rst) begin //active low reset just for fu
            counter<=32'd0;
        end else begin
            if(counter==PERIOD-1)
                counter<=32'd0;
            else
                counter<=counter+1;
        end
    end
    assign pulse = (counter == PERIOD-1); //feel free to change this later.
endmodule
 
`default_nettype wire