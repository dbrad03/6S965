module led_controller(
        input wire clk,
        input wire rst,
        input wire en,
        input wire go_up,
        input wire go_down,
        input wire stop,
        output logic[3:0] q
    );
    enum {STOP,SCROLL_UP,SCROLL_DOWN} state;
    initial begin
        q = 4'b0001;
        state = STOP;
    end
    
    always_ff @(posedge clk)begin
        if (rst)begin
            q <= 4'b0001;
            state <= STOP;
        end else begin
            case (state)
                STOP: begin
                    // stay frozen
                end
                SCROLL_UP: begin
                    if (en) begin
                        if (q==4'b1000) begin
                            q <= 4'b0001;
                        end else begin
                            q <= q<<1;
                        end
                    end
                end
                SCROLL_DOWN: begin
                    if (en) begin
                        if (q==4'b0001) begin
                            q <= 4'b1000;
                        end else begin
                            q <= q>>1;
                        end
                    end
                end
            endcase

            if (stop) begin state <= STOP; end
            else if (go_up) begin state <= SCROLL_UP; end
            else if (go_down) begin state <= SCROLL_DOWN; end
        end
    end
endmodule
