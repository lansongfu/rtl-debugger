`timescale 1ns/1ps

module param_test #(
    parameter WIDTH = 8,
    parameter DEPTH = 16
)(
    input [WIDTH-1:0] din,
    output [WIDTH-1:0] dout
);

    // localparam 测试
    localparam ADDR_WIDTH = 5;
    localparam MAX_COUNT = DEPTH - 1;
    
    reg [WIDTH-1:0] data_reg;
    reg [ADDR_WIDTH-1:0] addr_reg;
    wire [WIDTH-1:0] processed_data;
    
    // 使用参数的 assign
    assign dout = processed_data;
    assign processed_data = data_reg;
    
    always @(posedge clk) begin
        data_reg <= din;
        addr_reg <= addr_reg + 1'b1;
    end

endmodule
