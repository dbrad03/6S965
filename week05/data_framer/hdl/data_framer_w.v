module data_framer_w #
	(
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 32
	)
	(
        input wire pixel_clk, //driven by video pixel clock
        input wire [23:0] pixel_data, //24 bit true color video data
        input wire trigger,
 
		// Ports of Axi Master Bus Interface M00_AXIS
		input wire  m00_axis_tready,
		output wire  m00_axis_tvalid, m00_axis_tlast,
		output wire [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output wire [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb
	);
 
    data_framer mdf
    (   .pixel_clk(pixel_clk),
        .pixel_data(pixel_data),
        .trigger(trigger),
        .m00_axis_tready(m00_axis_tready),
        .m00_axis_tvalid(m00_axis_tvalid),
        .m00_axis_tlast(m00_axis_tlast),
        .m00_axis_tdata(m00_axis_tdata),
        .m00_axis_tstrb(m00_axis_tstrb)
    );
endmodule