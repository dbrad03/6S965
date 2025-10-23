module fir_15
	(
        input wire clk,
        input wire rst,
        input wire signed [31:0] data_in,
        input wire data_in_valid,
        input wire signed [14:0][7:0] coeffs,
        output logic signed [31:0] data_out,
        output logic data_out_valid
	);
    localparam NUM_COEFFS = 15;
    logic signed [NUM_COEFFS-1:0][31:0] buffer;
    integer i;

    initial begin
        for (i = 0; i < NUM_COEFFS; i = i + 1) begin
            buffer[i] = 0;
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < NUM_COEFFS; i = i + 1) begin
                buffer[i] <= 0;
            end
            data_out <= 0;
            data_out_valid <= 0;
        end else begin
            if (data_in_valid) begin

                buffer[0] <= data_in * $signed(coeffs[NUM_COEFFS-1]);
            
                for (i = 1; i < NUM_COEFFS-1; i = i + 1) begin
                    buffer[i] <= $signed(buffer[i-1]) + (data_in * $signed(coeffs[NUM_COEFFS-1-i]));
                end
                
                data_out <= $signed(buffer[NUM_COEFFS-2]) + (data_in * $signed(coeffs[0]));
            end
            data_out_valid <= data_in_valid;
        end
    end

endmodule
