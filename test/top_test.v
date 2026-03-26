
module top(
    input clk,
    input rst_n,
    input [7:0] data_in,
    output [7:0] data_out
);
    wire [7:0] mid_data;
    
    sub_module u_sub (
        .clk(clk),
        .rst_n(rst_n),
        .data_in(data_in),
        .data_out(mid_data)
    );
    
    assign data_out = mid_data;
endmodule
