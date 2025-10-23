module spi_tx_w(
     input wire clk,
     input wire rst,
     input wire [63:0] data_in,
     input wire trigger,
     output wire copi,
     output wire dclk,
     output wire cs
    );
    spi_tx  #(.DATA_WIDTH(64), .DATA_CLK_PERIOD(20))
    mspi
    (   .clk(clk),
        .rst(~rst), //IMPOTANT!!!
        .data_in(data_in),
        .trigger(trigger),
        .copi(copi),
        .dclk(dclk),
        .cs(cs));
endmodule
