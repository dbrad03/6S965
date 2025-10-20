`default_nettype none
`timescale 1ns / 1ps

module axis_cordic #(
    parameter int C_S00_AXIS_TDATA_WIDTH = 32,
    parameter int C_M00_AXIS_TDATA_WIDTH = 32,
    parameter int NUM_STAGES             = 16,
    parameter int DATA_WIDTH             = 16,
    parameter int ANGLE_WIDTH            = 16
) (
    // AXI-Stream slave (input) interface
    input  wire                                 s00_axis_aclk,
    input  wire                                 s00_axis_aresetn,
    input  wire                                 s00_axis_tlast,
    input  wire                                 s00_axis_tvalid,
    input  wire [C_S00_AXIS_TDATA_WIDTH-1:0]    s00_axis_tdata,
    input  wire [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] s00_axis_tstrb,
    output wire                                 s00_axis_tready,

    // AXI-Stream master (output) interface
    input  wire                                 m00_axis_aclk,
    input  wire                                 m00_axis_aresetn,
    input  wire                                 m00_axis_tready,
    output wire                                 m00_axis_tvalid,
    output wire                                 m00_axis_tlast,
    output wire [C_M00_AXIS_TDATA_WIDTH-1:0]    m00_axis_tdata,
    output wire [(C_M00_AXIS_TDATA_WIDTH/8)-1:0] m00_axis_tstrb
);

    function automatic signed [ANGLE_WIDTH-1:0] atan_lut (input int idx);
        case (idx)
            0:  atan_lut = 16'sh2000;
            1:  atan_lut = 16'sh12E4;
            2:  atan_lut = 16'sh09FB;
            3:  atan_lut = 16'sh0511;
            4:  atan_lut = 16'sh028B;
            5:  atan_lut = 16'sh0146;
            6:  atan_lut = 16'sh00A3;
            7:  atan_lut = 16'sh0051;
            8:  atan_lut = 16'sh0029;
            9:  atan_lut = 16'sh0014;
            10: atan_lut = 16'sh000A;
            11: atan_lut = 16'sh0005;
            12: atan_lut = 16'sh0003;
            13: atan_lut = 16'sh0001;
            14: atan_lut = 16'sh0001;
            15: atan_lut = 16'sh0000;
            default: atan_lut = '0;
        endcase
    endfunction
    
    localparam signed [16:0] K_INV = 17'sh09B75; // 0.607252935 in Q1.16 format

    logic signed [DATA_WIDTH+1:0]  x_reg      [NUM_STAGES-1:0];
    logic signed [DATA_WIDTH+1:0]  y_reg      [NUM_STAGES-1:0];
    logic signed [DATA_WIDTH+1:0]  z_reg      [NUM_STAGES-1:0];
    // Store original input signs: bit0 -> original x sign (1 when x<0), bit1 -> original y sign (1 when y<0)
    logic                   [1:0]  rotated    [NUM_STAGES-1:0];
    logic                                  tvalid_pipe [NUM_STAGES-1:0];
    logic                                  tlast_pipe  [NUM_STAGES-1:0];
    logic [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] tstrb_pipe  [NUM_STAGES-1:0];

    logic signed [DATA_WIDTH+16:0] mag_prod;
    logic signed [DATA_WIDTH+16:0] mag_scaled;
    logic                   [15:0] magnitude;
    logic signed [ANGLE_WIDTH+1:0] angle_rot;
    logic signed [ANGLE_WIDTH+1:0] angle_clamp;
    logic        [ANGLE_WIDTH+1:0] angle_reg;
    logic        [ANGLE_WIDTH-1:0] angle;

    assign mag_scaled = (x_reg[NUM_STAGES-1] * K_INV) >>> 16;
    assign magnitude = (mag_scaled <= 0) ? 16'b0 : (mag_scaled > 17'sh0FFFF) ? 16'hFFFF : mag_scaled[15:0];

    assign angle_rot = rotated[NUM_STAGES-1][0] ?
                        (rotated[NUM_STAGES-1][1] ? -z_reg[NUM_STAGES-1] - 18'sh08000 :
                                                    -z_reg[NUM_STAGES-1] + 18'sh08000) :
                            -z_reg[NUM_STAGES-1];
    assign angle_clamp = angle_rot + 18'sh10000;
    assign angle     = (angle_rot < 0 ) ? angle_clamp[ANGLE_WIDTH-1:0] : angle_rot[ANGLE_WIDTH-1:0];

    assign m00_axis_tvalid =                     tvalid_pipe[NUM_STAGES-1];
    assign m00_axis_tlast  =                      tlast_pipe[NUM_STAGES-1];
    assign m00_axis_tstrb  =                      tstrb_pipe[NUM_STAGES-1];
    assign m00_axis_tdata  =                             {angle,magnitude};
    assign s00_axis_tready = m00_axis_tready || ~tvalid_pipe[NUM_STAGES-1];

    logic signed [DATA_WIDTH+1:0]  x_start;
    logic signed [DATA_WIDTH+1:0]  y_start;
    assign x_start = s00_axis_tdata[15] ? -$signed(s00_axis_tdata[15:0]) : $signed(s00_axis_tdata[15:0]);
    assign y_start = s00_axis_tdata[15] ? -$signed(s00_axis_tdata[31:16]) : $signed(s00_axis_tdata[31:16]);

    always_ff @(posedge s00_axis_aclk) begin
        if (s00_axis_aresetn==0) begin
            for (integer i = 0; i < NUM_STAGES; i = i + 1) begin
                x_reg[i] <= 16'b0;
                y_reg[i] <= 16'b0;
                z_reg[i] <= 16'b0;
                rotated[i] <= 2'b0;
                tvalid_pipe[i] <= 16'b0;
                tlast_pipe[i] <= 16'b0;
                tstrb_pipe[i] <= 16'b0;
            end
        end else begin
            if (s00_axis_tready) begin
                // PASS VALUES DOWN PIPELINE
                for (integer i = 1; i < NUM_STAGES; i = i + 1) begin
                    rotated[i] <= rotated[i-1];
                    tvalid_pipe[i] <= tvalid_pipe[i-1];
                    tlast_pipe[i]  <= tlast_pipe[i-1];
                    tstrb_pipe[i]  <= tstrb_pipe[i-1];
                    if (~tvalid_pipe[i-1]) begin         
                        x_reg[i] <= x_reg[i-1];
                        y_reg[i] <= y_reg[i-1];
                        z_reg[i] <= z_reg[i-1];
                    end else begin
                        if (y_reg[i-1] >= 0) begin
                            x_reg[i] <= x_reg[i-1] + (y_reg[i-1]>>>i);
                            y_reg[i] <= y_reg[i-1] - (x_reg[i-1]>>>i);
                            z_reg[i] <= z_reg[i-1] - atan_lut(i);
                        end else begin
                            x_reg[i] <= x_reg[i-1] - (y_reg[i-1]>>>i);
                            y_reg[i] <= y_reg[i-1] + (x_reg[i-1]>>>i);
                            z_reg[i] <= z_reg[i-1] + atan_lut(i);
                        end
                    end
                end
                // PASS IN NEW DATA OR INVALID TO PIPELINE START
                if (s00_axis_tvalid) begin
                    rotated[0] <= {s00_axis_tdata[31],s00_axis_tdata[15]}; // {y_is_neg, x_is_neg}
                    x_reg[0]   <= (y_start >= 0) ? x_start + y_start : x_start - y_start;
                    y_reg[0]   <= (y_start >= 0) ? y_start - x_start : y_start + x_start;
                    z_reg[0]   <= (y_start >= 0) ? -atan_lut(0) :  atan_lut(0);
                    tvalid_pipe[0] <= 1'b1;
                    tlast_pipe[0]  <= s00_axis_tlast;
                    tstrb_pipe[0]  <= s00_axis_tstrb;
                end else begin
                    rotated[0] <= 2'b0;
                    x_reg[0] <= 16'b0;
                    y_reg[0] <= 16'b0;
                    z_reg[0]   <= 16'b0;
                    tvalid_pipe[0] <= 1'b0;
                    tlast_pipe[0] <= 1'b0;
                    tstrb_pipe[0] <= 1'b0;
                end
            end
        end
    end

endmodule

`default_nettype wire
