`timescale 1ns/1ps

module generate_if_test #(
    parameter ENABLE_FEATURE = 1
)(
    input clk,
    input data_in,
    output data_out
);

    wire feature_wire;
    wire bypass_wire;
    
    generate
        if (ENABLE_FEATURE) begin:feature_block
            reg feature_reg;
            always @(posedge clk)
                feature_reg <= data_in;
            assign feature_wire = feature_reg;
        end else begin:bypass_block
            assign feature_wire = data_in;
        end
    endgenerate
    
    assign data_out = feature_wire;

endmodule
