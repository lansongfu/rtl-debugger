// 错误设计 1: last 信号时序错拍（提前一拍）
// 问题：last 应该在数据最后一拍拉起，但组合逻辑导致提前

module tx_engine_wrong (
    input wire clk,
    input wire rst,
    input wire [7:0] data_in,
    input wire data_valid,
    input wire [2:0] count,
    output reg tx_done,
    output wire last  // ❌ 错误：组合逻辑，提前一拍
);

    // 计数器
    reg [2:0] cnt;
    always @(posedge clk or posedge rst)
        if (rst)
            cnt <= 0;
        else if (data_valid)
            cnt <= cnt + 1;
    
    // ❌ 错误：last 用组合逻辑，会提前一拍
    assign last = (cnt == 3'd7);  // 计数到 7 就拉高，但数据还在传输
    
    // 完成信号
    always @(posedge clk or posedge rst)
        if (rst)
            tx_done <= 0;
        else
            tx_done <= (cnt == 3'd7) && data_valid;

endmodule


// 正确设计：last 信号打拍（延迟一拍）
module tx_engine_correct (
    input wire clk,
    input wire rst,
    input wire [7:0] data_in,
    input wire data_valid,
    input wire [2:0] count,
    output reg tx_done,
    output reg last  // ✅ 正确：时序逻辑，打拍
);

    reg [2:0] cnt;
    reg last_comb;
    
    // 计数器
    always @(posedge clk or posedge rst)
        if (rst)
            cnt <= 0;
        else if (data_valid)
            cnt <= cnt + 1;
    
    // ✅ 正确：先组合逻辑判断
    assign last_comb = (cnt == 3'd7);
    
    // ✅ 再打拍输出
    always @(posedge clk or posedge rst)
        if (rst)
            last <= 0;
        else
            last <= last_comb;  // 延迟一拍，与数据对齐
    
    always @(posedge clk or posedge rst)
        if (rst)
            tx_done <= 0;
        else
            tx_done <= last && data_valid;

endmodule


// 错误设计 2: 状态机转换错拍
module state_machine_wrong (
    input wire clk,
    input wire rst,
    input wire start,
    input wire done,
    output reg busy,
    output reg complete
);

    reg [1:0] state;
    localparam IDLE = 0, BUSY = 1, DONE = 2;
    
    // ❌ 错误：状态转换和输出不在同一拍
    always @(posedge clk or posedge rst)
        if (rst)
            state <= IDLE;
        else
            case (state)
                IDLE: if (start) state <= BUSY;
                BUSY: if (done) state <= DONE;
                DONE: state <= IDLE;
            endcase
    
    // ❌ 错误：busy 用组合逻辑，会产生毛刺
    assign busy = (state == BUSY);
    
    // ❌ 错误：complete 提前一拍
    assign complete = (state == DONE);  // 应该在 DONE 状态保持一拍后再拉高

endmodule


// 错误设计 3: 计数器边界差一拍
module counter_off_by_one (
    input wire clk,
    input wire rst,
    input wire enable,
    output reg [3:0] count,
    output reg overflow
);

    // ❌ 错误：计数到 15 就溢出，应该是 16
    always @(posedge clk or posedge rst)
        if (rst) begin
            count <= 0;
            overflow <= 0;
        end else if (enable) begin
            if (count == 4'd15)  // ❌ 应该是 count == 4'd14
                overflow <= 1;   // 提前一拍溢出
            else
                count <= count + 1;
        end

endmodule


// 错误设计 4: 跨时钟域未同步 + 时序错拍
module cdc_timing_wrong (
    input wire clk_a,
    input wire clk_b,
    input wire rst_a,
    input wire rst_b,
    input wire pulse_in,  // clk_a 域脉冲
    output reg pulse_out  // clk_b 域输出
);

    // ❌ 错误：直接跨时钟域，无同步
    reg pulse_sync;
    always @(posedge clk_b or posedge rst_b)
        if (rst_b)
            pulse_sync <= 0;
        else
            pulse_sync <= pulse_in;  // ❌ 亚稳态风险
    
    // ❌ 错误：输出未打拍
    always @(posedge clk_b or posedge rst_b)
        if (rst_b)
            pulse_out <= 0;
        else
            pulse_out <= pulse_sync;  // 应该再打一拍

endmodule


// 错误设计 5: 使能信号时序不匹配
module enable_mismatch (
    input wire clk,
    input wire rst,
    input wire data_valid,
    input wire [7:0] data_in,
    output reg [7:0] data_out,
    output reg data_ready
);

    reg [2:0] delay_cnt;
    
    // 延迟计数器
    always @(posedge clk or posedge rst)
        if (rst)
            delay_cnt <= 0;
        else if (data_valid)
            delay_cnt <= delay_cnt + 1;
    
    // ❌ 错误：data_ready 和 data_out 时序不匹配
    always @(posedge clk or posedge rst)
        if (rst) begin
            data_out <= 0;
            data_ready <= 0;
        end else begin
            // data 延迟 3 拍
            if (delay_cnt == 3'd3)
                data_out <= data_in;
            
            // ❌ data_ready 延迟 2 拍，不匹配！
            if (delay_cnt == 3'd2)  // ❌ 应该是 3
                data_ready <= 1;
            else
                data_ready <= 0;
        end

endmodule
