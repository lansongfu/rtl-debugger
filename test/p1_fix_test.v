// Test for _parse_modules with parameter ports
module param_module #(parameter N=8, parameter M=16) (
    input [N-1:0] din,
    output [M-1:0] dout
);
    assign dout = din;
endmodule

// Test for nested parameter
module nested_param #(
    parameter WIDTH = 8,
    parameter DEPTH = WIDTH * 2
)(
    input clk,
    output data
);
    assign data = clk;
endmodule

// Test sub module for instance tests
module sub_module (
    input [7:0] a,
    input [7:0] b,
    output [7:0] y
);
    assign y = a & b;
endmodule

// Test for _parse_instances - should not match posedge/negedge/if/case
module instance_test (
    input clk,
    input rst_n,
    input [7:0] din,
    output [7:0] dout
);

    // Real instances
    sub_module u_sub (
        .a(din),
        .b(dout),
        .y(dout)
    );

    // Instance with bit-select port connection
    sub_module u_sub2 (
        .a(din[3:0]),
        .b({4{rst_n}}),
        .y(dout[7:4])
    );

    // Instance with concatenation port connection
    sub_module u_sub3 (
        .a({din[3:0], din[7:4]}),
        .b({rst_n, rst_n, rst_n, rst_n, rst_n, rst_n, rst_n, rst_n}),
        .y(dout)
    );

    // Parameterized instance
    param_module #(.N(16), .M(32)) u_param (
        .din(din),
        .dout(dout)
    );

    // This should NOT be parsed as instance
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dout <= 8'b0;
        end else begin
            case (din[1:0])
                2'b00: dout <= din;
                2'b01: dout <= ~din;
                default: dout <= 8'b0;
            endcase
        end
    end

endmodule
