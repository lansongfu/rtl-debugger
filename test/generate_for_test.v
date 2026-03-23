`timescale 1ns/1ps

module generate_for_test (
    input clk,
    input [7:0] data_in,
    output [7:0] data_out
);

    wire [7:0] stage;
    
    generate
        genvar i;
        for (i=0; i<8; i=i+1) begin:gen_stages
            reg stage_reg;
            always @(posedge clk) begin
                stage_reg <= data_in[i];
            end
            assign stage[i] = stage_reg;
        end
    endgenerate
    
    assign data_out = stage;

endmodule
