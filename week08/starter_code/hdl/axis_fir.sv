`default_nettype none
`timescale 1 ns / 1 ps

// FIR filter that can be parameterized to different numbers of taps.
module axis_fir #
	(
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 32,
        parameter integer NUM_COEFFS = 512
	)
	(

		// Ports of Axi Slave Bus Interface S00_AXIS
		input wire  s00_axis_aclk, s00_axis_aresetn,
		input wire  s00_axis_tlast, s00_axis_tvalid,
		input wire [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata,
		input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] s00_axis_tstrb,
		output logic  s00_axis_tready,

        input wire signed [NUM_COEFFS-1:0][7:0] coeffs,
		// Ports of Axi Master Bus Interface M00_AXIS
		input wire  m00_axis_tready,
		output logic  m00_axis_tvalid, m00_axis_tlast,
		output logic [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb
	);

    logic signed [31:0] intmdt_term [NUM_COEFFS -1:0];

    initial begin
        for(int i=0; i<NUM_COEFFS; i++)begin
            intmdt_term[i] = 0;
        end
    end

    assign s00_axis_tready = m00_axis_tready; //immediate (for now)

    logic signed [31:0] stdata;
    assign stdata = s00_axis_tdata;
    always_ff @(posedge s00_axis_aclk)begin
        m00_axis_tstrb <= s00_axis_tstrb;
        m00_axis_tlast <= s00_axis_tlast;
        m00_axis_tvalid <= s00_axis_tvalid;
        if (s00_axis_tvalid && s00_axis_tready)begin
            intmdt_term[0] <= $signed(coeffs[0])*$signed(stdata);
            for (int i=1; i<NUM_COEFFS; i=i+1)begin
                intmdt_term[i] <=  $signed(coeffs[i])*$signed(stdata) + $signed(intmdt_term[i-1]);
            end
        end
        if (!s00_axis_aresetn)begin
            m00_axis_tvalid <= 0;
            m00_axis_tlast <= 0;
            m00_axis_tstrb <= 0;
        end
    end
    assign m00_axis_tdata = intmdt_term[NUM_COEFFS-1];
endmodule

`default_nettype wire
