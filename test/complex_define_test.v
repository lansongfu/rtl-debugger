`timescale 1ns/1ps

// 带参数的宏
`define MUL(x, y) ((x) * (y))
`define MIN(a, b) ((a) < (b) ? (a) : (b))

// 简单宏
`define CLK_FREQ 100
`define RST_POLARITY 0

module complex_define_test (
    input clk,
    input rst_n,
    input [7:0] data_in,
    output [7:0] data_out
);

    reg [7:0] data_reg;
    wire [7:0] processed;
    
    // 使用宏
    assign data_out = processed;
    assign processed = data_reg;
    
    always @(posedge clk) begin
        if (!rst_n)
            data_reg <= 8'h0;
        else
            data_reg <= data_in;
    end

endmodule
