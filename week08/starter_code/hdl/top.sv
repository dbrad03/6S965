`default_nettype none
`timescale 1 ns / 1 ps

module top #
	(
        parameter integer SQUITTER_LENGTH = 112,
		parameter integer C_S00_AXIS_TDATA_WIDTH	= 32,
		parameter integer C_M00_AXIS_TDATA_WIDTH	= SQUITTER_LENGTH,
        parameter integer NUM_COEFFS_LOWPASS = 75,
        parameter integer NUM_COEFFS_PREAMBLE_DETECTOR = 512
	)
	(

		// Ports of Axi Slave Bus Interface S00_AXIS
        // Streams in I/Q data (I and Q are each 16 bit signed, packed into 32 bit stream).
		input wire  s00_axis_aclk, s00_axis_aresetn,
		input wire  s00_axis_tlast, s00_axis_tvalid,
		input wire [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata,
		input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] s00_axis_tstrb,
		output logic  s00_axis_tready,

		// Ports of Axi Master Bus Interface M00_AXIS
        // Outputs 112-bit ADS-B squitters. Ignores downstream ready signal
        // because the next thing is a FIFO that should always be ready (also
        // we don't care about losing a squitter occasionally).
		input wire  m00_axis_aclk, m00_axis_aresetn,
		input wire  m00_axis_tready,
		output logic  m00_axis_tvalid, m00_axis_tlast,
		output logic [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb,

        // FIR coefficients for the matched filter that detects the preamble.
        input wire signed [NUM_COEFFS_PREAMBLE_DETECTOR-1:0][7:0] preamble_coeffs,
        // FIR coefficients for the lowpass filter that is applied to the ADC data.
        input wire signed [NUM_COEFFS_LOWPASS-1:0][7:0] lowpass_coeffs,
        // Threshold used to decide whether a local maximum of the matched filter output is large enough to trigger the decoder state machine.
        input wire [C_S00_AXIS_TDATA_WIDTH-1:0] preamble_detector_threshold,
        // Threshold used to decide whether magnitude is a zero bit or a one bit.
        input wire [C_S00_AXIS_TDATA_WIDTH-1:0] decoder_threshold,
        // Thresholded magnitude data for debugging the decoder with the ILA.
        output wire thresholded_data_debug
	);

    // Split the incoming 32-bit data stream into two 16-bit signed integer data streams.
    logic signed [15:0] adc_data_real;
    logic signed [15:0] adc_data_imag;
    assign adc_data_real = s00_axis_tdata[31:16];
    assign adc_data_imag = s00_axis_tdata[15:0];

    // Lowpass filter the I (real) data stream.
    logic lowpass_filter_tvalid;
    logic signed [C_S00_AXIS_TDATA_WIDTH-1:0] lowpass_filter_real_tdata;
    axis_fir #(.NUM_COEFFS(NUM_COEFFS_LOWPASS)) lowpass_filter_real(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(1'b0),
        .s00_axis_tvalid(s00_axis_tvalid),
        .s00_axis_tdata({{16{adc_data_real[15]}}, adc_data_real}),
        .s00_axis_tstrb(4'b1111),
        .s00_axis_tready(s00_axis_tready),
        .coeffs(lowpass_coeffs),
        .m00_axis_tready(1'b1),
        .m00_axis_tvalid(lowpass_filter_tvalid),
        .m00_axis_tlast(),
        .m00_axis_tdata(lowpass_filter_real_tdata),
        .m00_axis_tstrb()
    );

    // Lowpass filter the Q (imaginary) data stream.
    logic signed [C_S00_AXIS_TDATA_WIDTH-1:0] lowpass_filter_imag_tdata;
    axis_fir #(.NUM_COEFFS(NUM_COEFFS_LOWPASS)) lowpass_filter_imag(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(1'b0),
        .s00_axis_tvalid(s00_axis_tvalid),
        .s00_axis_tdata({{16{adc_data_imag[15]}}, adc_data_imag}),
        .s00_axis_tstrb(4'b1111),
        .s00_axis_tready(),
        .coeffs(lowpass_coeffs),
        .m00_axis_tready(1'b1),
        .m00_axis_tvalid(),
        .m00_axis_tlast(),
        .m00_axis_tdata(lowpass_filter_imag_tdata),
        .m00_axis_tstrb()
    );

    // Divide the lowpassed data streams by 127 to counter the bit growth from the lowpass filters.
    logic signed [31:0] lowpass_filter_real_tdata_scaled;
    logic signed [31:0] lowpass_filter_imag_tdata_scaled;
    assign lowpass_filter_real_tdata_scaled = (lowpass_filter_real_tdata >>> 7);
    assign lowpass_filter_imag_tdata_scaled = (lowpass_filter_imag_tdata >>> 7);

    // Clip the lowpassed and scaled data streams to the 16-bit range in case they are still out of range.
    logic signed [15:0] lowpass_filter_real_tdata_clipped;
    logic signed [15:0] lowpass_filter_imag_tdata_clipped;
    assign lowpass_filter_real_tdata_clipped = (lowpass_filter_real_tdata_scaled < -32'sd32768) ? -32'sd32768 : ((lowpass_filter_real_tdata_scaled > 32'sd32767) ? 32'sd32767 : lowpass_filter_real_tdata_scaled);
    assign lowpass_filter_imag_tdata_clipped = (lowpass_filter_imag_tdata_scaled < -32'sd32768) ? -32'sd32768 : ((lowpass_filter_imag_tdata_scaled > 32'sd32767) ? 32'sd32767 : lowpass_filter_imag_tdata_scaled);

    // Feed the 16-bit filtered/scaled/clipped I/Q data into the CORDIC to calculate its magnitude.
    logic cordic_tvalid;
    logic cordic_tlast;
    logic [C_S00_AXIS_TDATA_WIDTH-1:0] cordic_tdata;
    logic [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] cordic_tstrb;
    cordic my_cordic(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(1'b0),
        .s00_axis_tvalid(lowpass_filter_tvalid),
        .s00_axis_tdata({lowpass_filter_real_tdata_clipped, lowpass_filter_imag_tdata_clipped}),
        .s00_axis_tstrb(4'b1111),
        .s00_axis_tready(),
        .m00_axis_tready(1'b1),
        .m00_axis_tvalid(cordic_tvalid),
        .m00_axis_tlast(cordic_tlast),
        .m00_axis_tdata(cordic_tdata),
        .m00_axis_tstrb(cordic_tstrb)
    );

    logic [15:0] cordic_magnitude;
    assign cordic_magnitude = cordic_tdata[15:0]; // Bottom 16 bits are the magnitude, top 16 bits are the angle (which we don't care about for AM).

    // Feed the magnitude signal from the CORDIC into the matched filter.
    logic matched_filter_tready;
    logic matched_filter_tvalid;
    logic matched_filter_tlast;
    logic [C_S00_AXIS_TDATA_WIDTH-1:0] matched_filter_tdata;
    logic [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] matched_filter_tstrb;
    axis_fir #(.NUM_COEFFS(NUM_COEFFS_PREAMBLE_DETECTOR)) preamble_detection_fir_filter (
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(cordic_tlast),
        .s00_axis_tvalid(cordic_tvalid),
        .s00_axis_tdata({16'b0, cordic_magnitude}),
        .s00_axis_tstrb(cordic_tstrb),
        .s00_axis_tready(),
        .coeffs(preamble_coeffs),
        .m00_axis_tready(matched_filter_tready),
        .m00_axis_tvalid(matched_filter_tvalid),
        .m00_axis_tlast(matched_filter_tlast),
        .m00_axis_tdata(matched_filter_tdata),
        .m00_axis_tstrb(matched_filter_tstrb)
    );

    // Detect large peaks in the output of the matched filter and pulse trigger high when one is detected.
    logic trigger;
    preamble_detector my_preamble_detector(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(matched_filter_tlast),
        .s00_axis_tvalid(matched_filter_tvalid),
        .s00_axis_tdata(matched_filter_tdata),
        .s00_axis_tstrb(matched_filter_tstrb),
        .s00_axis_tready(matched_filter_tready),
        .trigger(trigger),
        .preamble_detector_threshold(preamble_detector_threshold)
    );

    // State machine that starts decoding ADS-B packets from the magnitude data (NOT the matched filter data) when trigger is detected.
    adsb_decoder my_adsb_decoder(
        .s00_axis_aclk(s00_axis_aclk),
        .s00_axis_aresetn(s00_axis_aresetn),
        .s00_axis_tlast(s00_axis_tlast),
        .s00_axis_tvalid(s00_axis_tvalid),
        .s00_axis_tdata({16'b0, cordic_magnitude}),
        .s00_axis_tstrb(s00_axis_tstrb),
        .trigger(trigger),
        .decoder_threshold(decoder_threshold),
        .m00_axis_tdata(m00_axis_tdata),
        .m00_axis_tvalid(m00_axis_tvalid),
        .m00_axis_tlast(m00_axis_tlast),
        .m00_axis_tstrb(m00_axis_tstrb),
        .thresholded_data_debug(thresholded_data_debug)
    );

endmodule
