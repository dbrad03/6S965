module divider #(parameter WIDTH = 32)
    (   input wire clk_in,
        input wire rst_in,
        input wire[WIDTH-1:0] dividend_in,
        input wire[WIDTH-1:0] divisor_in,
        input wire data_valid_in,
        output logic[WIDTH-1:0] quotient_out,
        output logic[WIDTH-1:0] remainder_out,
        output logic data_valid_out,
        output logic error_out,
        output logic busy_out
    );
    logic [WIDTH-1:0] quotient, dividend;
    logic [WIDTH-1:0] divisor;
    logic [5:0] count;
    logic [31:0] p;
    enum {IDLE, DIVIDING} state;
    always_ff @(posedge clk_in)begin
        if (rst_in)begin
            quotient <= 0;
            dividend <= 0;
            divisor <= 0;
            remainder_out <= 0;
            busy_out <= 1'b0;
            error_out <= 1'b0;
            state <= IDLE;
            data_valid_out <= 1'b0;
            count <= 0;
        end else begin
            case (state)
                IDLE: begin
                    if (data_valid_in)begin
                        if (divisor_in==0)begin
                            quotient_out <= 0;
                            remainder_out <= 0;
                            data_valid_out <= 1;
                            error_out <= 1;
                            busy_out <= 0;
                            state <= IDLE;
                        end else begin
                            state <= DIVIDING;
                            quotient <= 0;
                            dividend <= dividend_in;
                            divisor <= divisor_in;
                            busy_out <= 1'b1;
                            error_out <= 1'b0;
                            count <= 31;//load all up
                            p <= 0;
                            data_valid_out <= 0;
                        end
                    end else begin
                        data_valid_out <= 1'b0;
                    end
                end
                DIVIDING: begin
                    if (count==0)begin
                        state <= IDLE;
                        if ({p[30:0],dividend[31]}>=divisor[31:0])begin
                            remainder_out <= {p[30:0],dividend[31]} - divisor[31:0];
                            quotient_out <= {dividend[30:0],1'b1};
                        end else begin
                            remainder_out <= {p[30:0],dividend[31]};
                            quotient_out <= {dividend[30:0],1'b0};
                        end
                        busy_out <= 1'b0; //tell outside world i'm done
                        error_out <= 1'b0;
                        data_valid_out <= 1'b1; //good stuff!
                    end else begin
                        if ({p[30:0],dividend[31]}>=divisor[31:0])begin
                            p <= {p[30:0],dividend[31]} - divisor[31:0];
                            dividend <= {dividend[30:0],1'b1};
                        end else begin
                            p <= {p[30:0],dividend[31]};
                            dividend <= {dividend[30:0],1'b0};
                        end
                            count <= count-1;
                    end
                end
            endcase
        end
    end
endmodule
