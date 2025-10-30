`timescale 1ns / 1ps
`default_nettype none
module cordic #(
    parameter integer C_S00_AXIS_TDATA_WIDTH = 32,
    parameter integer C_M00_AXIS_TDATA_WIDTH = 32,
    parameter integer C_NUM_CORDIC_ITERATIONS = 16,
    parameter integer C_CORDIC_FRAC_WIDTH = 16,
    parameter integer C_CORDIC_GAIN = 39796
)(
    // Ports of Axi Slave Bus Interface S00_AXIS
    input wire s00_axis_aclk,
    input wire s00_axis_aresetn,
    input wire s00_axis_tlast,
    input wire s00_axis_tvalid,
    input wire [C_S00_AXIS_TDATA_WIDTH-1:0] s00_axis_tdata,
    input wire [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] s00_axis_tstrb,
    output logic s00_axis_tready,

    // Ports of Axi Master Bus Interface M00_AXIS
    input wire m00_axis_tready,
    output logic m00_axis_tvalid,
    output logic m00_axis_tlast,
    output logic [C_M00_AXIS_TDATA_WIDTH-1:0] m00_axis_tdata, // [15:0] is magnitude (unsigned 16-bit integer). [31:16] is angle.
    output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1:0] m00_axis_tstrb
);
    localparam integer C_CORDIC_LOG2_FRAC_WIDTH = $clog2(C_CORDIC_FRAC_WIDTH);
    localparam integer C_CORDIC_FIXED_WIDTH = (C_S00_AXIS_TDATA_WIDTH/2) + C_CORDIC_FRAC_WIDTH + 1; // +1 is hack to make everything positive

    logic [15:0] angles [0:15];

    initial begin
        angles[0] = 16'd8191;
        angles[1] = 16'd4835;
        angles[2] = 16'd2555;
        angles[3] = 16'd1297;
        angles[4] = 16'd651;
        angles[5] = 16'd325;
        angles[6] = 16'd162;
        angles[7] = 16'd81;
        angles[8] = 16'd40;
        angles[9] = 16'd20;
        angles[10] = 16'd10;
        angles[11] = 16'd5;
        angles[12] = 16'd2;
        angles[13] = 16'd1;
        angles[14] = 16'd0;
        angles[15] = 16'd0;
    end
    // Helper functions
    function logic [C_CORDIC_FIXED_WIDTH-1:0] rnd2zerodiv(
        input logic signed [C_CORDIC_FIXED_WIDTH-1:0] x,
        input logic [C_CORDIC_LOG2_FRAC_WIDTH-1:0] i
    );
        logic sign;
        if ($signed(x) < 0) begin
            x = -x;
            sign = 1;
        end else begin
            sign = 0;
        end

        x = x >> i;

        if (sign) begin
            rnd2zerodiv = -x;
        end else begin
            rnd2zerodiv = x;
        end
    endfunction

    initial begin
        assert(C_CORDIC_FRAC_WIDTH == 16) else $fatal("C_CORDIC_FRAC_WIDTH must be 16, or fix the CORDIC gain const.");
    end

    function logic [C_CORDIC_FIXED_WIDTH-1:0] abs_scale(
        input logic signed [C_S00_AXIS_TDATA_WIDTH/2-1:0] x
    );
        if ($signed(x) < 0) begin
            abs_scale = $signed(-x) * $signed(C_CORDIC_GAIN);
        end else begin
            abs_scale = x * C_CORDIC_GAIN;
        end
    endfunction

    // Pipeline registers
    logic signed [C_CORDIC_FIXED_WIDTH-1:0] x_i [0:C_NUM_CORDIC_ITERATIONS];
    logic signed [C_CORDIC_FIXED_WIDTH-1:0] y_i [0:C_NUM_CORDIC_ITERATIONS];
    logic signed [C_CORDIC_FIXED_WIDTH-1:0] z_i [0:C_NUM_CORDIC_ITERATIONS];
    logic  flips_i [0:C_NUM_CORDIC_ITERATIONS];
    logic tvalid_i [0:C_NUM_CORDIC_ITERATIONS];
    logic tlast_i [0:C_NUM_CORDIC_ITERATIONS];

    // Initial inputs (scale the absolute value)
    logic signed [C_S00_AXIS_TDATA_WIDTH/2-1:0] pre_x_i_0, pre_y_i_0;
    logic signed [C_S00_AXIS_TDATA_WIDTH/2-1:0] x_i_0, y_i_0, z_i_0;
    logic flips_i_0;
    assign pre_x_i_0 = s00_axis_tdata[(C_S00_AXIS_TDATA_WIDTH/2)-1:0];
    assign pre_y_i_0 = s00_axis_tdata[(C_S00_AXIS_TDATA_WIDTH-1):(C_S00_AXIS_TDATA_WIDTH/2)];
    assign x_i_0 = pre_x_i_0<0?-pre_x_i_0:pre_x_i_0;
    assign y_i_0 = pre_x_i_0<0?-pre_y_i_0:pre_y_i_0;
    assign z_i_0 = 0;
    assign flips_i_0 = pre_x_i_0<0;

    always_ff @(posedge s00_axis_aclk) begin
        if (m00_axis_tready) begin
            tvalid_i[0] <= s00_axis_tvalid;
            tlast_i[0] <= s00_axis_tlast;
            x_i[0] <= abs_scale(x_i_0);
            y_i[0] <= abs_scale(y_i_0);
            z_i[0] <= 0;
            flips_i[0] <= flips_i_0;
        end
    end

    // Pipeline stages
    genvar i;
    generate for (i = 0; i < C_NUM_CORDIC_ITERATIONS; i = i + 1) begin: cordic_iteration
        always_ff @(posedge s00_axis_aclk) begin
            if (m00_axis_tready) begin
                tvalid_i[i+1] <= tvalid_i[i];
                tlast_i[i+1] <= tlast_i[i];
                flips_i[i+1] <= flips_i[i];
                if ($signed(y_i[i]) < 0) begin
                    x_i[i+1] <= x_i[i] - rnd2zerodiv(y_i[i], i);
                    y_i[i+1] <= y_i[i] + rnd2zerodiv(x_i[i], i);
                    z_i[i+1] <= z_i[i] - angles[i];
                end else begin
                    x_i[i+1] <= x_i[i] + rnd2zerodiv(y_i[i], i);
                    y_i[i+1] <= y_i[i] - rnd2zerodiv(x_i[i], i);
                    z_i[i+1] <= z_i[i] + angles[i];
                end
            end
        end
    end endgenerate

    logic [15:0] mag;
    logic [15:0] rotate_angle, regular_angle;
    assign rotate_angle     = z_i[C_NUM_CORDIC_ITERATIONS]-32768;
    assign regular_angle    =  z_i[C_NUM_CORDIC_ITERATIONS];
    assign mag =  x_i[C_NUM_CORDIC_ITERATIONS][C_CORDIC_FIXED_WIDTH-2:C_CORDIC_FRAC_WIDTH];
    assign m00_axis_tvalid = tvalid_i[C_NUM_CORDIC_ITERATIONS];
    assign m00_axis_tlast = tlast_i[C_NUM_CORDIC_ITERATIONS];
    //assign m00_axis_tdata = x_i[C_NUM_CORDIC_ITERATIONS][C_CORDIC_FIXED_WIDTH-2:C_CORDIC_FRAC_WIDTH]; // remove the extra bit with -2 instead of -1
    always_comb begin
        if (flips_i[C_NUM_CORDIC_ITERATIONS]) begin
            m00_axis_tdata = {rotate_angle, mag};
        end else begin
            m00_axis_tdata = {regular_angle, mag};
        end
    end

    // Pass through ready and strb
    assign s00_axis_tready = m00_axis_tready;
    assign m00_axis_tstrb = 4'hf;
endmodule

`default_nettype wire
