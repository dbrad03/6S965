`default_nettype none
 
module axis_fir_15 #
    (
        parameter int C_S00_AXIS_TDATA_WIDTH    = 32,
        parameter int C_M00_AXIS_TDATA_WIDTH    = 32,
        parameter int NUM_COEFFS               = 15
    )
    (

        // Ports of Axi Slave Bus Interface S00_AXIS
        input  wire                            s00_axis_aclk,
        input  wire                            s00_axis_aresetn,
        input  wire                            s00_axis_tlast,
        input  wire                            s00_axis_tvalid,
        input  wire signed [C_S00_AXIS_TDATA_WIDTH-1 : 0] s00_axis_tdata,
        input  wire [(C_S00_AXIS_TDATA_WIDTH/8)-1: 0]     s00_axis_tstrb,
        output logic                           s00_axis_tready,

        // FIR coefficients
        input  wire signed [NUM_COEFFS-1:0][7:0]           coeffs,

        // Ports of Axi Master Bus Interface M00_AXIS
        input  wire                            m00_axis_aclk,
        input  wire                            m00_axis_aresetn,
        input  wire                            m00_axis_tready,
        output logic                           m00_axis_tvalid,
        output logic                           m00_axis_tlast,
        output logic signed [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata,
        output logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0]     m00_axis_tstrb
    );

    //i previously used some intermediate terms and then inialized them all
    //to zero
    logic signed [31:0] intmdt_term [NUM_COEFFS -1:0];
    initial begin
        for(int i=0; i<NUM_COEFFS; i++)begin
            intmdt_term[i] = 0;
        end
        $display("DONE!");
    end
 
    logic m00_axis_tvalid_reg, m00_axis_tlast_reg;
    logic signed [C_M00_AXIS_TDATA_WIDTH-1 : 0] m00_axis_tdata_reg;
    logic [(C_M00_AXIS_TDATA_WIDTH/8)-1: 0] m00_axis_tstrb_reg;
 
    assign m00_axis_tvalid = m00_axis_tvalid_reg;
    assign m00_axis_tlast = m00_axis_tlast_reg;
    assign m00_axis_tdata = m00_axis_tdata_reg;
    assign m00_axis_tstrb = m00_axis_tstrb_reg;
    assign s00_axis_tready = ~m00_axis_tvalid_reg || m00_axis_tready;

    always_ff @(posedge s00_axis_aclk)begin
        if (s00_axis_aresetn==0)begin
            for (int i = 0; i < NUM_COEFFS; i = i + 1) begin
                intmdt_term[s] <= 0;
            end
            m00_axis_tvalid_reg <= 0;
            m00_axis_tlast_reg <= 0;
            m00_axis_tdata_reg <= 0;
            m00_axis_tstrb_reg <= 0;
        end else begin
            if (s00_axis_tready & s00_axis_tvalid)begin
                m00_axis_tlast_reg <= s00_axis_tlast;
                m00_axis_tstrb_reg <= s00_axis_tstrb;
                m00_axis_tvalid_reg <= 1'b1;

                intmdt_term[0] <= s00_axis_tdata * coeffs[0];
                for (int i = 1; i < NUM_COEFFS-1; i = i + 1) begin
                    intmdt_term[i] <= intmdt_term[i-1] + (s00_axis_tdata * coeffs[i]);
                end
                m00_axis_tdata_reg <= intmdt_term[NUM_COEFFS-2] + (s00_axis_tdata * coeffs[NUM_COEFFS-1]);
            end else if (m00_axis_tready && m00_axis_tvalid_reg) begin
                m00_axis_tvalid_reg <= 1'b0;
            end
        end
    end
 
endmodule
 
`default_nettype wire
