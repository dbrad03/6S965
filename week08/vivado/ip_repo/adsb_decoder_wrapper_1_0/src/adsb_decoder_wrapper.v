
`timescale 1 ns / 1 ps

	module adsb_decoder_wrapper #
	(
		// Users to add parameters here

		// User parameters ends
		// Do not modify the parameters beyond this line


		// Parameters of Axi Slave Bus Interface S00_AXIS
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,

		// Parameters of Axi Master Bus Interface M00_AXIS
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 128,
		parameter integer C_M00_AXIS_START_COUNT	= 32
	)
	(
		// Users to add ports here

		// User ports ends
		// Do not modify the ports beyond this line


		// Ports of Axi Slave Bus Interface S00_AXIS
		input wire  s00_axis_aclk,
		input wire  s00_axis_aresetn,
		output wire  s00_axis_tready,
		input wire [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata,
		input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1 : 0] s00_axis_tstrb,
		input wire  s00_axis_tlast,
		input wire  s00_axis_tvalid,

		// Ports of Axi Master Bus Interface M00_AXIS
		input wire  m00_axis_aclk,
		input wire  m00_axis_aresetn,
		output wire  m00_axis_tvalid,
		output wire [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output wire [(C_M00_AXIS_TDATA_WIDTH/8)-1 : 0] m00_axis_tstrb,
		output wire  m00_axis_tlast,
		input wire  m00_axis_tready,
		
		output wire thresholded_data_debug,
		output wire [31:0] raw_data_debug
	);

    assign raw_data_debug = {16'b0, s00_axis_tdata[15:0]};

	// Add user logic here
    top my_top(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
		.s00_axis_tlast(s00_axis_tlast),
		.s00_axis_tvalid(s00_axis_tvalid),
		.s00_axis_tdata(s00_axis_tdata),
		.s00_axis_tstrb(s00_axis_tstrb),
		.s00_axis_tready(s00_axis_tready),

		.m00_axis_aclk(m00_axis_aclk),
		.m00_axis_aresetn(m00_axis_aresetn),
		.m00_axis_tready(m00_axis_tready),
		.m00_axis_tvalid(m00_axis_tvalid),
		.m00_axis_tlast(m00_axis_tlast),
		.m00_axis_tdata(m00_axis_tdata),
		.m00_axis_tstrb(m00_axis_tstrb),

        .preamble_coeffs(4096'h101010101010101010101010101010101010101010101010101010101010101000000000000000000000000000000000000000000000000000000000000000001010101010101010101010101010101010101010101010101010101010101010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010101010101010101010101010101010101010101010101010101010101010100000000000000000000000000000000000000000000000000000000000000000101010101010101010101010101010101010101010101010101010101010101),
        .lowpass_coeffs(600'h100000000000000fffffffffefefefefefefefefeffff0000010203040506070708090909090909090807070605040302010000fffffefefefefefefefefeffffffff0000000000000001),
        .preamble_detector_threshold(32'd2000),
        .decoder_threshold(32'd20),
        .thresholded_data_debug(thresholded_data_debug)
    );
	// User logic ends

	endmodule
