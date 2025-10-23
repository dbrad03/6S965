`timescale 1ns / 1ps
`default_nettype none
//////////////////////////////////////////////////////////////////////////////////
// Company:
// Engineer:  Joe Steinmeyer
//
// Create Date: 09/12/2025 05:11:30 AM
// Module Name: fir_wrapper
// Project Name: week03 6.S965 Fall 2025
// Target Devices: 7000 series Zynq (7020 on Pynq Z2)
// Tool Versions: (Vivado 2025.1)
// Description:  wraps up three separate fir_15 devices (one for each color channel
// handles splitting the pixel up into channels and putting back together
// as well as having spots for offset binary conversion, shifting the outputs of the
// FIR and doing clipping (completed by student).
//
// Dependencies: fir_15 from work earlier in week.
//
// Revision:
// Revision 0.01 - File Created
//
//////////////////////////////////////////////////////////////////////////////////


module fir_wrapper(
	input wire clk,
	input wire rst,

	input wire hsync_in,
	input wire vsync_in,
	input wire vde_in,
    input wire [23:0] pixel_in,

	output wire hsync_out,
	output wire vsync_out,
	output wire vde_out,
    output wire [23:0] pixel_out,

    input wire [2:0] color_select,
    input wire [7:0] scaler,
    input wire [14:0][7:0] coeffs,
    input wire ob,
    
    input wire [3:0] btns,
    output wire trig

    );
    assign trig = btns[0];
    
    reg   hsync_pipe [2:0];
    reg   vsync_pipe [2:0];
    reg   vde_pipe [2:0];
    reg   [23:0] pixel_pipe [2:0];

    wire signed [31:0] fir_pixel[2:0]; //r,g,b
    reg signed [31:0] shifted_pixel[2:0]; //r,g,b
    reg signed [31:0] clipped_pixel[2:0]; //r,g,b

    always @(posedge clk)begin
        hsync_pipe[2]  <= hsync_in;
        vsync_pipe[2]  <= vsync_in;
        vde_pipe[2]    <= vde_in;
        pixel_pipe[2] <= pixel_in;
        hsync_pipe[1] <= hsync_pipe[2];
        vsync_pipe[1] <= vsync_pipe[2];
        vde_pipe[1] <= vde_pipe[2];
        pixel_pipe[1] <= pixel_pipe[2];
        hsync_pipe[0] <= hsync_pipe[1];
        vsync_pipe[0] <= vsync_pipe[1];
        vde_pipe[0] <= vde_pipe[1];
        pixel_pipe[0] <= pixel_pipe[1];
    end

    assign hsync_out = hsync_pipe[0];
    assign vsync_out = vsync_pipe[0];
    assign vde_out = vde_pipe[0];

    reg signed [31:0] ob_pixel[2:0];

    //offset binary conversion (if active):
    always @(*)begin
        ob_pixel[0] = ob ? {24'b0, pixel_in[7:0]}-128   : {24'b0, pixel_in[7:0]};
        ob_pixel[1] = ob ? {24'b0, pixel_in[15:8]}-128  : {24'b0, pixel_in[15:8]};
        ob_pixel[2] = ob ? {24'b0, pixel_in[23:16]}-128 : {24'b0, pixel_in[23:16]};
    end

    //make three parallel pipes for red, green, and blue channels
    //all have 8 bit inputs and outputs, though 32 bits intermediate before clip
    generate
        genvar i;
        for (i=0; i<3; i=i+1)begin
            fir_15(     .clk(clk),
                        .rst(rst),
                        .data_in(ob_pixel[i]),
                        .data_in_valid(vde_in),
                        .coeffs(coeffs),
                        .data_out(fir_pixel[i]),
                        .data_out_valid()
                );
            always @(posedge clk)begin
                if (rst)begin
                    shifted_pixel[i] <= 32'b0;
                end else begin
                    //6S965 Student: CHANGE ME!!!
                    shifted_pixel[i] <= fir_pixel[i]>>>scaler;
                end
            end
            always @(posedge clk)begin
                if (rst)begin
                    clipped_pixel[i] <= 32'b0;
                end else begin
                    if (ob)begin
                        //6S965 Student: CHANGE ME!!!
                        clipped_pixel[i] <= (shifted_pixel[i] < -128) ? -128 : (shifted_pixel[i] > 127) ? 127 : shifted_pixel[i];
                    end else begin
                        //6S965 Student: CHANGE ME!!!
                        clipped_pixel[i] <= (shifted_pixel[i] < 0) ? 0 : (shifted_pixel[i] > 255) ? 255 : shifted_pixel[i];
                    end
                end
            end
        end
    endgenerate

    reg [7:0] r,g,b;
    reg [7:0] cob_pixel [2:0];

    //undoing offset binary conversion:
    always @(*)begin
        cob_pixel[0] = ob?clipped_pixel[0]+128:clipped_pixel[0];
        cob_pixel[1] = ob?clipped_pixel[1]+128:clipped_pixel[1];
        cob_pixel[2] = ob?clipped_pixel[2]+128:clipped_pixel[2];
    end

    //choosing whether to use unmodified color channel or FIR-done channel:
    always @(*)begin
        g = color_select[0]?cob_pixel[0]:pixel_pipe[0][7:0];
        b = color_select[1]?cob_pixel[1]:pixel_pipe[0][15:8];
        r = color_select[2]?cob_pixel[2]:pixel_pipe[0][23:16];
    end

    //for debugging: pushing input buttons turns off selected channel:
    assign pixel_out = {btns[2]?8'b0:r,btns[1]?8'b0:b,btns[0]?8'b0:g};


endmodule


`default_nettype wire
