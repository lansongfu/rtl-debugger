// 跨模块追踪测试用例
module sub_module(
    input clk,
    input rst_n,
    input [7:0] data_in,
    input valid_in,
    output reg [7:0] data_out,
    output reg valid_out
);

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_out <= 8'b0;
        valid_out <= 1'b0;
    end else if (valid_in) begin
        data_out <= data_in;
        valid_out <= 1'b1;
    end else begin
        valid_out <= 1'b0;
    end
end

endmodule

module mid_module(
    input clk,
    input rst_n,
    input [7:0] rx_data,
    input rx_valid,
    output [7:0] tx_data,
    output tx_valid
);

wire [7:0] sub_data_out;
wire sub_valid_out;

sub_module u_sub(
    .clk(clk),
    .rst_n(rst_n),
    .data_in(rx_data),
    .valid_in(rx_valid),
    .data_out(sub_data_out),
    .valid_out(sub_valid_out)
);

assign tx_data = sub_data_out;
assign tx_valid = sub_valid_out;

endmodule

module top_module(
    input clk,
    input rst_n,
    input [7:0] din,
    input din_valid,
    output [7:0] dout,
    output dout_valid
);

wire [7:0] mid_tx_data;
wire mid_tx_valid;

mid_module u_mid(
    .clk(clk),
    .rst_n(rst_n),
    .rx_data(din),
    .rx_valid(din_valid),
    .tx_data(mid_tx_data),
    .tx_valid(mid_tx_valid)
);

assign dout = mid_tx_data;
assign dout_valid = mid_tx_valid;

endmodule
