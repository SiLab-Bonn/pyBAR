`timescale 1ns / 1ps

// synchronize flag (signal lasts just one clock cycle) to new clock domain (CLK_B), with busy and task done

module task_domain_crossing(
    input wire      CLK_A,
    input wire      CLK_B,
    input wire      FLAG_IN_CLK_A,
    output wire     FLAG_OUT_CLK_B,
    output wire     BUSY_CLK_A,
    output wire     BUSY_CLK_B,
    output wire     TASK_DONE_CLK_A,
    input wire      TASK_DONE_CLK_B,
    input wire      DISABLE_CLK_A
);

// reg DISABLE_FF_CLK_A;
// always @(posedge CLK_A)
    // DISABLE_FF_CLK_A <= DISABLE_CLK_A;

// wire RESET_CLK_A;
// assign RESET_CLK_A = ~DISABLE_FF_CLK_A & DISABLE_CLK_A

reg FLAG_TOGGLE_CLK_A, FLAG_TOGGLE_CLK_B, BUSY_HOLD_CLK_B;
reg [2:0] SYNC_CLK_B, SYNC_CLK_A;

always @(posedge CLK_A) if(~DISABLE_CLK_A & FLAG_IN_CLK_A & ~BUSY_CLK_A) FLAG_TOGGLE_CLK_A <= ~FLAG_TOGGLE_CLK_A;

always @(posedge CLK_B) SYNC_CLK_B <= {SYNC_CLK_B[1:0], FLAG_TOGGLE_CLK_A};
assign FLAG_OUT_CLK_B = (SYNC_CLK_B[2] ^ SYNC_CLK_B[1]);
assign BUSY_CLK_B = FLAG_OUT_CLK_B | BUSY_HOLD_CLK_B;
always @(posedge CLK_B) BUSY_HOLD_CLK_B <= ~TASK_DONE_CLK_B & BUSY_CLK_B;
always @(posedge CLK_B) if(BUSY_CLK_B & TASK_DONE_CLK_B) FLAG_TOGGLE_CLK_B <= FLAG_TOGGLE_CLK_A;

always @(posedge CLK_A) SYNC_CLK_A <= {SYNC_CLK_A[1:0], FLAG_TOGGLE_CLK_B};
assign BUSY_CLK_A = FLAG_TOGGLE_CLK_A ^ SYNC_CLK_A[2];
assign TASK_DONE_CLK_A = SYNC_CLK_A[2] ^ SYNC_CLK_A[1];


endmodule
