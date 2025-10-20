`default_nettype none

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
            0:  atan_lut = 16'sd8192;
            1:  atan_lut = 16'sd4836;
            2:  atan_lut = 16'sd2555;
            3:  atan_lut = 16'sd1297;
            4:  atan_lut = 16'sd651;
            5:  atan_lut = 16'sd326;
            6:  atan_lut = 16'sd163;
            7:  atan_lut = 16'sd81;
            8:  atan_lut = 16'sd41;
            9:  atan_lut = 16'sd20;
            10: atan_lut = 16'sd10;
            11: atan_lut = 16'sd5;
            12: atan_lut = 16'sd3;
            13: atan_lut = 16'sd1;
            14: atan_lut = 16'sd1;
            15: atan_lut = 16'sd0;
            default: atan_lut = '0;
        endcase
    endfunction
    
    localparam signed [16:0] K_INV = 17'sd39797; // 0.607252935 in Q1.GAIN_FRAC

    logic signed [DATA_WIDTH-1:0]  x_reg      [NUM_STAGES-1:0];
    logic signed [DATA_WIDTH-1:0]  y_reg      [NUM_STAGES-1:0];
    logic signed [DATA_WIDTH-1:0]  z_reg      [NUM_STAGES-1:0];
    logic                          rotated    [NUM_STAGES-1:0];
    logic                                  tvalid_pipe [NUM_STAGES-1:0];
    logic                                  tlast_pipe  [NUM_STAGES-1:0];
    logic [(C_S00_AXIS_TDATA_WIDTH/8)-1:0] tstrb_pipe  [NUM_STAGES-1:0];

    logic                  [31:0] mag_prod;
    logic                  [31:0] magnitude;
    logic signed [DATA_WIDTH-1:0] angle;
    assign mag_prod = (x_reg[NUM_STAGES-1] * K_INV)>>16;
    assign magnitude = (mag_prod <= 0) ? 16'b0 : (mag_prod > 16'sd65535) ? 16'hFFFF : mag_prod;
    assign angle     = rotated[NUM_STAGES-1] ? z_reg[NUM_STAGES-1] + 16'sh8000: z_reg[NUM_STAGES-1];

    assign m00_axis_tvalid =                     tvalid_pipe[NUM_STAGES-1];
    assign m00_axis_tlast  =                      tlast_pipe[NUM_STAGES-1];
    assign m00_axis_tstrb  =                      tstrb_pipe[NUM_STAGES-1];
    assign m00_axis_tdata  =                       {angle,magnitude[15:0]};
    assign s00_axis_tready = m00_axis_tready || ~tvalid_pipe[NUM_STAGES-1];

    logic signed [DATA_WIDTH-1:0]  x_start;
    logic signed [DATA_WIDTH-1:0]  y_start;
    assign x_start = s00_axis_tdata[15] ? -s00_axis_tdata[15:0] : s00_axis_tdata[15:0];
    assign y_start = s00_axis_tdata[15] ? -s00_axis_tdata[31:16] : s00_axis_tdata[31:16];

    always_ff @(posedge s00_axis_aclk) begin
        if (s00_axis_aresetn==0) begin
            for (integer i = 0; i < NUM_STAGES; i = i + 1) begin
                x_reg[0] <= 16'b0;
                y_reg[0] <= 16'b0;
                z_reg[0] <= 16'b0;
                rotated[0] <= 16'b0;
                tvalid_pipe[0] <= 16'b0;
                tlast_pipe[0] <= 16'b0;
                tstrb_pipe[0] <= 16'b0;
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
                        if (y_reg[i-1] > 0) begin
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
                    rotated[0] <= s00_axis_tdata[15];
                    x_reg[0]   <= (y_start > 0) ? x_start + y_start : x_start - y_start;
                    y_reg[0]   <= (y_start > 0) ? y_start - x_start : y_start + x_start;
                    z_reg[0]   <= (y_start > 0) ? -atan_lut(0) : atan_lut(0);
                    tvalid_pipe[0] <= 1'b1;
                    tlast_pipe[0]  <= s00_axis_tlast;
                    tstrb_pipe[0]  <= s00_axis_tstrb;
                end else begin
                    rotated[0] <= 1'b0;
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
