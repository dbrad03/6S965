`default_nettype none
`timescale 1 ns / 1 ps

// Detects when we see a local maximum (x[i-1] < x && x[i+1] < x) that is greater than the threshold.
module preamble_detector #
	(
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 32
	)
	(
		// Ports of Axi Slave Bus Interface S00_AXIS
		input wire  s00_axis_aclk, s00_axis_aresetn,
		input wire  s00_axis_tlast, s00_axis_tvalid,
		input wire [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata,
		input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] s00_axis_tstrb,
		output logic  s00_axis_tready,

        input wire [C_S00_AXIS_TDATA_WIDTH - 1:0] preamble_detector_threshold,
        output wire trigger
	);

    assign s00_axis_tready = 1'b1;

    // 3-element pipeline of the last 3 pieces of data that came in.
    logic [C_S00_AXIS_TDATA_WIDTH - 1: 0] lookback_window [2:0];

    logic local_maximum;
    assign local_maximum = lookback_window[1] > lookback_window[0] && lookback_window[1] > lookback_window[2];

    // Trigger goes high only when we see a local maximum of sufficiently high value.
    assign trigger = local_maximum && lookback_window[1] >= preamble_detector_threshold;

    always_ff @(posedge s00_axis_aclk) begin
        if (~s00_axis_aresetn) begin
            for (integer i = 0; i < 2; i = i + 1) begin
                lookback_window[i] <= 0;
            end
        end
        else begin
            if (s00_axis_tvalid) begin
                // Add data to the lookback pipeline that determines local maxima.
                lookback_window[0] <= s00_axis_tdata;
                lookback_window[1] <= lookback_window[0];
                lookback_window[2] <= lookback_window[1];
            end
        end
    end

endmodule
