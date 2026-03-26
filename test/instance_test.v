
module top(
    input clk,
    input rst_n,
    input [7:0] data_in,
    output [7:0] data_out
);
    wire [7:0] mid_data;
    
    // 正确的实例化
    fifo #(.DATA_WIDTH(8)) u_fifo (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(mid_data)
    );
    
    reg [7:0] data_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            data_reg <= 0;
        else if (data_valid)
            data_reg <= mid_data;
    end
    
    assign data_out = data_reg;
endmodule
