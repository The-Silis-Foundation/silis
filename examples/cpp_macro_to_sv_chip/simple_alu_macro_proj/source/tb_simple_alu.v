`timescale 1ns/1ps
module tb_simple_alu;
    reg clk = 0;
    reg rst_n = 0;
    reg [7:0] data_in = 8'hAA;
    wire [7:0] data_out;

    simple_alu dut (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(data_out)
    );

    always #5 clk = ~clk;

    initial begin
        #20 rst_n = 1;
        #100 $finish;
    end
endmodule
