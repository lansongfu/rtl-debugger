module always_test(
    input wire clk,
    input wire rst_n,
    input wire enable,
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output reg valid
);

// 时序逻辑：异步复位
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_out <= 8'h0;
        valid <= 1'b0;
    end else if (enable) begin
        data_out <= data_in;
        valid <= 1'b1;
    end
end

// 组合逻辑
wire next_valid;
assign next_valid = data_out[0] & valid;

endmodule
