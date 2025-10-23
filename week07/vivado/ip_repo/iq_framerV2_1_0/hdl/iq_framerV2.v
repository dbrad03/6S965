
`timescale 1 ns / 1 ps

	module iq_framerV2 #
	(
		// Users to add parameters here

		// User parameters ends
		// Do not modify the parameters beyond this line


		// Parameters of Axi Slave Bus Interface S01_AXIS
		parameter integer C_S01_AXIS_TDATA_WIDTH	= 32,

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


		// Ports of Axi Slave Bus Interface S01_AXIS
		input wire  s01_axis_aclk,
		input wire  s01_axis_aresetn,
		output wire  s01_axis_tready,
		input wire [C_S01_AXIS_TDATA_WIDTH/2-1 : 0] s01_axis_tdata,
		input wire [(C_S01_AXIS_TDATA_WIDTH/8)-1 : 0] s01_axis_tstrb,
		input wire  s01_axis_tlast,
		input wire  s01_axis_tvalid,

		// Ports of Axi Slave Bus Interface S00_AXIS
		input wire  s00_axis_aclk,
		input wire  s00_axis_aresetn,
		output wire  s00_axis_tready,
		input wire [C_S00_AXIS_TDATA_WIDTH/2-1 : 0] s00_axis_tdata,
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
		output reg [3:0] probe,
		input wire [3:0] control
	);
    
	// Add user logic here
	reg [17:0] s_counter;
	wire [17:0] count_to;
	assign count_to = (control==4'b0001) ? 18'h0FFFF : 18'h3FFFF; //65535 or 262143 default
	
	reg m00_axis_tvalid_reg, m00_axis_tlast_reg;
	reg signed [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata_reg;
	reg [(C_M00_AXIS_TDATA_WIDTH/8)-1 : 0] m00_axis_tstrb_reg;
	
    
    assign m00_axis_tvalid = s00_axis_tvalid && s01_axis_tvalid;
    assign m00_axis_tlast  = (s_counter == count_to-1) ? 1'b1: 1'b0;
    assign m00_axis_tstrb  = 4'b1111;
    assign m00_axis_tdata = control==2?{count_to[15:0], count_to[15:0]}: // display value we're counting to
	                        control==3?{s_counter, s_counter}: // display the count
	                        {s01_axis_tdata, s00_axis_tdata}; // pass in I/Q data
    
    assign s00_axis_tready = m00_axis_tready || ~m00_axis_tvalid_reg; // don't really need this

    
    always @(posedge s00_axis_aclk) begin
        if (s00_axis_aresetn==0) begin
            m00_axis_tvalid_reg <= 0;
            m00_axis_tlast_reg <= 0;
            m00_axis_tdata_reg <= 0;
            m00_axis_tstrb_reg <= 0;
            s_counter <= 0;
            probe <= 4'b0001;
        end else begin
            if (m00_axis_tvalid && m00_axis_tready) begin // s00_axis_tvalid && s01_axis_tvalid && m00_axis_tready
                s_counter <= (s_counter == count_to-1) ? 18'b0 : s_counter + 1;
                probe <= control;
            end
        end
    end


	// User logic ends

	endmodule
