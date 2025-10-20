`timescale 1ns / 1ps
`default_nettype none

//based on nice walkthrough and design here:
//https://fpgacpu.ca/fpga/Pipeline_Skid_Buffer.html

module axis_skid_buffer #
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

		// Ports of Axi Master Bus Interface M00_AXIS
		input wire  m00_axis_aclk, m00_axis_aresetn,
		input wire  m00_axis_tready,
		output logic  m00_axis_tvalid, m00_axis_tlast,
		output logic [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
		output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb
	);

  logic use_buffered_data;
  logic data_buffer_wren;
  logic data_out_wren;

  logic [C_S00_AXIS_TDATA_WIDTH-1:0] data_buffer_out;
  logic [C_S00_AXIS_TDATA_WIDTH-1:0] selected_data;

  logic [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] strb_buffer_out;
  logic [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0] selected_strb;

  logic last_buffer_out;
  logic selected_last;

  typedef enum { EMPTY, BUSY, FULL } state_t;
  state_t state;
  state_t state_next;

  logic insert, remove;
  logic load, flow, fill, flush, unload;
  // logic dump, pass; // for circular buffer

  always_comb begin
    selected_data = (use_buffered_data == 1'b1) ? data_buffer_out : s00_axis_tdata;
    selected_strb = (use_buffered_data == 1'b1) ? strb_buffer_out : s00_axis_tstrb;
    selected_last = (use_buffered_data == 1'b1) ? last_buffer_out : s00_axis_tlast;
    
    insert = s00_axis_tvalid == 1'b1 && s00_axis_tready == 1'b1; // valid in + downstream ready
    remove = m00_axis_tvalid == 1'b1 && m00_axis_tready == 1'b1; // data consumed
  
    load   = (state == EMPTY) && (insert == 1'b1) && (remove == 1'b0);
    flow   = (state == BUSY)  && (insert == 1'b1) && (remove == 1'b1);
    fill   = (state == BUSY)  && (insert == 1'b1) && (remove == 1'b0);
    unload = (state == BUSY)  && (insert == 1'b0) && (remove == 1'b1);
    flush  = (state == FULL)  && (insert == 1'b0) && (remove == 1'b1);
    // dump   = (state == FULL)  && (insert == 1'b1) && (remove == 1'b0);
    // pass   = (state == FULL)  && (insert == 1'b1) && (remove == 1'b1);

    state_next = state_t'((load   == 1'b1) ? BUSY  : state);
    state_next = state_t'((flow   == 1'b1) ? BUSY  : state_next);
    state_next = state_t'((fill   == 1'b1) ? FULL  : state_next);
    state_next = state_t'((flush  == 1'b1) ? BUSY  : state_next);
    state_next = state_t'((unload == 1'b1) ? EMPTY : state_next);
    // state_next = (dump   == 1'b1) ? FULL  : state_next;
    // state_next = (pass   == 1'b1) ? FULL  : state_next;

    data_out_wren     = (load  == 1'b1) || (flow == 1'b1) || (flush == 1'b1); //|| (dump == 1'b1) || (pass == 1'b1);
    data_buffer_wren  = (fill  == 1'b1)                                     ; //|| (dump == 1'b1) || (pass == 1'b1);
    use_buffered_data = (flush == 1'b1)                                     ; //|| (dump == 1'b1) || (pass == 1'b1);
  end
  
  always_ff @(posedge s00_axis_aclk) begin
    if (s00_axis_aresetn == 0) begin
      data_buffer_out <= 32'h0;
      strb_buffer_out <= 4'b1111;
      last_buffer_out <= 1'b0;
      m00_axis_tdata <= 32'h0;
      m00_axis_tstrb <= 4'b1111;
      m00_axis_tlast <= 1'b0;
      m00_axis_tvalid <= 1'b0;
      s00_axis_tready <= 1'b1;
      state <= EMPTY;  
    end else begin
      data_buffer_out <= data_buffer_wren ? s00_axis_tdata : data_buffer_out;
      m00_axis_tdata  <= data_out_wren    ? selected_data  : m00_axis_tdata;

      strb_buffer_out <= data_buffer_wren ? s00_axis_tstrb : strb_buffer_out;
      m00_axis_tstrb  <= data_out_wren    ? selected_strb  : m00_axis_tstrb;

      last_buffer_out <= data_buffer_wren ? s00_axis_tlast : last_buffer_out;
      m00_axis_tlast  <= data_out_wren    ? selected_last  : m00_axis_tlast;

      s00_axis_tready <= state_next != FULL;
      m00_axis_tvalid <= state_next != EMPTY;

      state <= state_next;
    end
  end

endmodule

`default_nettype wire