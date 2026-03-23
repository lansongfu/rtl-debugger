`timescale 1ns/1ps

module nested_include_test (
    input clk,
    output out
);

    `include "level1.vh"
    
    wire internal;
    assign out = internal;
    assign internal = level1_signal;

endmodule
