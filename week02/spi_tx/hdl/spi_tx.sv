`timescale 1ns / 1ps
`default_nettype none // prevents system from inferring an undeclared logic (good practice)
module spi_tx
   #(   parameter DATA_WIDTH = 8,
        parameter DATA_CLK_PERIOD = 100
    )
    ( input wire clk,
      input wire rst,
      input wire [DATA_WIDTH-1:0] data_in,
      input wire trigger,
      output logic busy,
      output logic copi, //Controller Out Peripheral In
      output logic dclk, //Data Clock
      output logic cs //Chip Select
    );
    logic [DATA_WIDTH-1:0] data;
    logic [$clog2(DATA_WIDTH)-1:0] data_idx;
    logic [$clog2(DATA_CLK_PERIOD>>1)-1:0] count;

    always_ff @(posedge clk) begin
        if (rst) begin
            data<=0;
            busy<=0;
            copi<=0;
            dclk<=0;
            count<=0;
            data_idx<=0;
            cs<=1;
        end else begin
            if (!busy&trigger&cs) begin
                data <= data_in;
                copi <= data_in[DATA_WIDTH-1];
                dclk <= 0;
                busy <= 0;
                cs <= 0;
                busy <= 1;
                count <= 0;
                data_idx <= DATA_WIDTH-1;
            end else begin
                // @ dclk edge
                if (count == (DATA_CLK_PERIOD>>1)-1) begin
                    dclk <= ~dclk;
                    count <= 0;
                    if (dclk) begin // @ falling edge
                        copi <= data[data_idx-1];
                        if (data_idx!=0) begin
                            data_idx <= data_idx - 1;
                        end else begin // @ end of transmission
                            busy <= 0;
                            cs <= 1;
                            dclk <= 0;
                            data <= 0;
                        end 
                    end
                end else begin
                    count <= count + 1;
                end
            end

        end
    end
endmodule
`default_nettype wire // prevents system from inferring an undeclared logic (good practice)
