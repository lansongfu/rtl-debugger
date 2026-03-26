
module top(
    input [31:0] data_in,
    output [31:0] data_out
);
    wire [7:0] byte0, byte1, byte2, byte3;
    wire [1:0] ctrl;
    
    // 位选连接
    slice_8bit u_slice0 (
        .data_in(data_in[7:0]),
        .data_out(byte0)
    );
    
    slice_8bit u_slice1 (
        .data_in(data_in[15:8]),
        .data_out(byte1)
    );
    
    // 拼接连接
    concat_4x8 u_concat (
        .byte0(byte0),
        .byte1(byte1),
        .byte2(byte2),
        .byte3(byte3),
        .data_out(data_out)
    );
    
    // 复制连接
    wire rst_n = 1'b1;
    reg [3:0] rst_sync;
    assign rst_sync = {4{rst_n}};
    
endmodule

module slice_8bit(
    input [7:0] data_in,
    output [7:0] data_out
);
    assign data_out = data_in;
endmodule
