
`timescale 1 ns / 1 ps

	module math_doer #
	(
		// Users to add parameters here
 
		// User parameters ends
		// Do not modify the parameters beyond this line
 
 
		// Parameters of Axi Slave Bus Interface S00_AXIS
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,
 
		// Parameters of Axi Master Bus Interface M00_AXIS
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 32,
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
		input wire  m00_axis_tready
	);
  //throw out the caca that xilinx put here and replace with our module
  //there stuff is good, but we don't need it. We're making a simple
  //passthrough calculator-type device that handles AXIS spec on its own
  //either by being simple (the 3*x+10000 thing) or by designing it into
  //the the module (the FIR15 filter hopefully)
 
  j_math (  .s00_axis_aclk(s00_axis_aclk),
            .s00_axis_aresetn(s00_axis_aresetn),
            .s00_axis_tready(s00_axis_tready),
            .s00_axis_tdata(s00_axis_tdata),
            .s00_axis_tstrb(s00_axis_tstrb),
            .s00_axis_tlast(s00_axis_tlast),
            .s00_axis_tvalid(s00_axis_tvalid),
 
            .m00_axis_aclk(m00_axis_aclk),
            .m00_axis_aresetn(m00_axis_aresetn),
            .m00_axis_tready(m00_axis_tready),
            .m00_axis_tdata(m00_axis_tdata),
            .m00_axis_tstrb(m00_axis_tstrb),
            .m00_axis_tlast(m00_axis_tlast),
            .m00_axis_tvalid(m00_axis_tvalid)
        );
	endmodule