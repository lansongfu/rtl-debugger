
module fsm(
    input clk,
    input rst_n,
    input [1:0] state_in,
    output reg [1:0] state_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state_out <= 2'b00;
        else begin
            case (state_in)
                2'b00: state_out <= 2'b01;
                2'b01: state_out <= 2'b10;
                2'b10: state_out <= 2'b11;
                2'b11: state_out <= 2'b00;
                default: state_out <= 2'b00;
            endcase
        end
    end
endmodule
