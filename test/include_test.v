`timescale 1ns/1ps

module include_test (
    input clk,
    output out
);

    // Include 头文件
    `include "defs.vh"
    
    wire test_wire;
    
    // 直接使用 include 中的信号
    assign out = test_wire;
    assign test_wire = global_signal;

endmodule
