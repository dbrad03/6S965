module data_framer #
	(
		parameter integer C_M00_AXIS_TDATA_WIDTH	= 32
	)
	(
        input  wire                         pixel_clk,
        input  wire [23:0]                  pixel_data,
        input  wire                         trigger,
		// Ports of Axi Master Bus Interface M00_AXIS
		input  wire                         m00_axis_tready,
		output logic                        m00_axis_tvalid,
        output logic                        m00_axis_tlast,
		output logic [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb
	);
 
    //You want to send up TLAST-framed bursts of data that are 2**16 in length
    //update and test this module to make sure that's happening.

    logic trigger_sync [1:0];
    logic [7:0] debounce_cycles = 8'h0;
    logic trigger_debounced = 1'b0;

    logic [15:0] samples     = 16'h0;
    logic        transmitting    = 1'b0;
    // logic        transmitting = 1'b0;
    wire  handshake;

    assign handshake = transmitting && m00_axis_tready;

    always_ff @(posedge pixel_clk) begin
        trigger_sync[0] <= trigger;
        trigger_sync[1] <= trigger_sync[0]; // sync trigger and debounce below

        if (!trigger_sync[1]) begin
            debounce_cycles <= 8'h0;
        end else if (!(&debounce_cycles)) begin
            debounce_cycles <= debounce_cycles + 8'h01;
        end

        trigger_debounced <= trigger_sync[1] && (debounce_cycles == 8'hFE);
        transmitting <= (trigger_debounced) ? 1'b1 : (transmitting && handshake && (samples==16'hFFFF)) ? 1'b0 : transmitting;
        samples <= (!transmitting) ? 16'b0 : (!handshake) ? samples : (samples==16'hFFFF) ? 16'b0 : samples + 1;
        // transmitting <= tx_state;
    end

    always_ff @(posedge pixel_clk) begin
        m00_axis_tvalid <= transmitting;
        m00_axis_tlast  <= transmitting && (samples == 16'hFFFF);
        m00_axis_tdata  <= {8'b0, pixel_data};
        m00_axis_tstrb  <= 4'b111;
    end

endmodule
