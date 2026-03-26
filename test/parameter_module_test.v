
module fifo #(
    parameter DATA_WIDTH = 8,
    parameter DEPTH = 16
) (
    input clk,
    input rst_n,
    input [DATA_WIDTH-1:0] data_in,
    output [DATA_WIDTH-1:0] data_out
);
    reg [DATA_WIDTH-1:0] data_reg;
    always @(posedge clk) begin
        if (!rst_n)
            data_reg <= 0;
        else
            data_reg <= data_in;
    end
    assign data_out = data_reg;
endmodule
