`default_nettype none
`timescale 1 ns / 1 ps

module adsb_decoder #
	(
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,
        parameter integer SQUITTER_LENGTH = 112,
		parameter integer C_M00_AXIS_TDATA_WIDTH	= SQUITTER_LENGTH
	)
	(
		// Ports of Axi Slave Bus Interface S00_AXIS
		input wire  s00_axis_aclk, s00_axis_aresetn,
		input wire  s00_axis_tlast, s00_axis_tvalid,
		input wire [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata, // Magnitude data from the CORDIC.
		input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] s00_axis_tstrb,
		output logic  s00_axis_tready,

		// Ports of Axi Master Bus Interface M00_AXIS
		output logic  m00_axis_tvalid, m00_axis_tlast,
		output logic [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata, // Outputs 112-bit ADS-B squitters. Ignore downstream ready because we have a FIFO downstream.
		output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb,

        input wire trigger,
        input wire [C_S00_AXIS_TDATA_WIDTH-1:0] decoder_threshold, // Threshold used to decide if magnitude is a 0-bit or 1-bit.
        
        output wire thresholded_data_debug // Helpful for debugging with the ILA.
	);

    assign s00_axis_tready = 1'b1;
    assign m00_axis_tstrb = 14'b1111_1111_1111_11;
    assign m00_axis_tlast = 1'b1;

    localparam integer BIT_LENGTH = 32; // 0.5 microsecond bit is 32 samples at 64 MSps
    logic [$clog2(SQUITTER_LENGTH) - 1:0] bit_counter; // Count how many data bits of the squitter we have received (increments every 2 physical bits).
    logic [$clog2(BIT_LENGTH) - 1:0] sample_counter; // Count ADC data samples to determine when we should sample each physical bit.
    logic thresholded_data;
    assign thresholded_data = (s00_axis_tdata > decoder_threshold);
    enum {IDLE, COUNT_FIRST_BIT, COUNT_SECOND_BIT} state; // IDLE state is for waiting for trigger. COUNT_FIRST_BIT state is for getting the 1st of each 2-physical-bit sequence that corresponds to 1 data bit. COUNT_SECOND_BIT is for getting the 2nd bit of each 2-physical-bit sequence and decoding a data bit.
    
    assign thresholded_data_debug = thresholded_data;

    logic sample_data, to_second_samp, first_data_bit, data_to_store;
    assign sample_data = sample_counter==BIT_LENGTH-1;
    assign data_to_store = (thresholded_data==0&&first_data_bit==1) ? 1'b1 :
                             (thresholded_data==1&&first_data_bit==0) ? 1'b0 : 1'bx;

    // TODO: You fill in this FSM. Remember to sample in the middle of bits like we do for UART, not at the start or end. You can implement this however you want (feel free to delete my skeleton and comments). Make sure your counting is correct! If you are off by 1 every time, the error will compound over 224 bits such that you are completely misaligned by the end. For debugging/simulation purposes, you could add a "sampling" signal that goes high whenever you sample the thresholded data. That would let you quickly tell in GTKWave whether your sampling is aligned to the center of each bit correctly the whole time.
    always_ff @(posedge s00_axis_aclk) begin
        if (~s00_axis_aresetn) begin
            state <= IDLE;
            sample_counter <= 0;
            bit_counter <= 0;
        end
        else begin
            case (state)
                IDLE: begin
                    // This state waits for trigger to go high.
                    // When trigger goes high, we start the sample counter at 3 (to deal with the slight delay from the local max detector) 
                    // and reset the bit counter to 0 since we are starting a new squitter. Then we go to the COUNT_FIRST_BIT state. 
                    if (trigger) begin 
                        sample_counter <= 3;
                        bit_counter <= 0;
                        state <= COUNT_FIRST_BIT;
                    end
                    m00_axis_tvalid <= 0;
                end
                COUNT_FIRST_BIT: begin
                    // This state uses sample_counter to count up to BIT_LENGTH - 1 (unless we are on the first bit, in which case we count up to BIT_LENGTH / 2). 
                    // When we reach the sample count, we sample the thresholded data, then go to the COUNT_SECOND_BIT state.
                    if ((bit_counter==0 && sample_counter==BIT_LENGTH>>1) || sample_data) begin
                        state <= COUNT_SECOND_BIT;
                        sample_counter <= 0;
                        first_data_bit <= thresholded_data;
                    end else begin
                        sample_counter <= sample_counter + 1;
                    end 
                end
                COUNT_SECOND_BIT: begin
                    // This state uses sample_counter to count up to BIT_LENGTH - 1, at which point is samples the thresholded data. 
                    // It then uses the saved first bit from COUNT_SECOND_BIT and the sampled thresholded data to decide what the data bit is ("10" -> "1", "01" -> "0" in Manchester coding).
                    // If we have done SQUITTER_LENGTH data bits, then we set valid high and return to the IDLE state. 
                    // Otherwise, we increment the bit_counter, reset the sample_counter, and go back to the COUNT_FIRST_BIT state.
                    if (sample_data) begin
                        if (bit_counter==SQUITTER_LENGTH-1) begin
                            m00_axis_tvalid <= 1;
                            state <= IDLE;
                            bit_counter <= 0;
                        end else begin
                            state <= COUNT_FIRST_BIT;
                            bit_counter <= bit_counter + 1;
                        end
                        m00_axis_tdata <= {m00_axis_tdata[C_M00_AXIS_TDATA_WIDTH-2:0], data_to_store};
                        sample_counter <= 0;
                    end else begin
                        sample_counter <= sample_counter + 1;
                    end
                end
            endcase
        end
    end

endmodule
