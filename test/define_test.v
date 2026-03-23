`timescale 1ns/1ps

// 定义测试宏
`define BUS_WIDTH 32
`define DATA_SIZE 8
`define ENABLE_FEATURE 1

module define_test (
    input [`BUS_WIDTH-1:0] data_in,
    output [`DATA_SIZE-1:0] data_out
);

    wire [`BUS_WIDTH-1:0] internal_bus;
    reg [`DATA_SIZE-1:0] result;
    
    // 使用宏的 assign
    assign data_out = result;
    
    // 条件编译（会保留信号）
    `ifdef ENABLE_FEATURE
    wire feature_signal;
    assign feature_signal = 1'b1;
    `endif
    
    always @(posedge clk) begin
        result <= data_in[`DATA_SIZE-1:0];
    end

endmodule
