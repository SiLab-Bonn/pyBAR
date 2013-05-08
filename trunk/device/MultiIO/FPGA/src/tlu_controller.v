/*  _____ _   _   _ 
 * |_   _| | | | | |
 *   | | | |_| |_| |
 *   |_| |___|\___/
 *
 * TLU controller supporting EUDET TLU 0.1/0.2
 */
 
 `default_nettype none
 
 module tlu_controller (
    input wire                  BUS_CLK,
    input wire                  BUS_RST,
    input wire      [15:0]      BUS_ADD,
    input wire      [7:0]       BUS_DATA_IN,
    input wire                  BUS_RD,
    input wire                  BUS_WR,
    output reg      [7:0]       BUS_DATA_OUT,
    
    input wire                  CLK_160,
    input wire                  CLK_40,
    input wire                  CLK_5,
    
    input wire                  RJ45_TRIGGER,
    input wire                  LEMO_TRIGGER,
    input wire                  RJ45_RESET,
    input wire                  LEMO_RESET,
    output reg                  RJ45_ENABLED,
    output wire                 TLU_BUSY,
    output wire                 TLU_CLOCK,
    output wire                 TLU_RESET_FLAG,
    
    input wire                  CMD_READY,
    output wire                 CMD_EXT_START_FLAG,
    input wire                  CMD_EXT_START_ENABLE,
    
    output wire                 TLU_DATA_SAVE_SIGNAL,
    output wire                 TLU_DATA_SAVE_FLAG,
    // FIXME: temporary assigned internally to make TLU running
    //input wire                  TLU_DATA_SAVED_FLAG,
    output wire     [31:0]      TLU_DATA,              // TLU trigger parallel data
    output wire                 TLU_TRIGGER_ABORT,
    
    input wire                  FIFO_NEAR_FULL
);

wire SOFT_RST; //Address: 0
assign SOFT_RST = (BUS_ADD==0 && BUS_WR);
wire RST;
assign RST = BUS_RST || SOFT_RST;

// write reg
reg [7:0] status_regs[7:0];

// Register 0 for SOFT_RST
wire [1:0] TLU_MODE; // 2'b00 - RJ45 disabled, 2'b01 - TLU no handshake, 2'b10 - TLU simple handshake, 2'b11 - TLU trigger data handshake
assign TLU_MODE = status_regs[1][1:0];
wire TLU_TRIGGER_DATA_MSB_FIRST; // set endianness of TLU number
assign TLU_TRIGGER_DATA_MSB_FIRST = status_regs[1][2];
wire TLU_TRIGGER_CLOCK_INVERT;
assign TLU_TRIGGER_CLOCK_INVERT = status_regs[1][3];
wire [3:0] TLU_TRIGGER_DATA_DELAY;
assign TLU_TRIGGER_DATA_DELAY = status_regs[1][7:4];
wire [4:0] TLU_TRIGGER_CLOCK_CYCLES;
assign TLU_TRIGGER_CLOCK_CYCLES = status_regs[2][4:0];
wire [2:0] reg_2_spare;
assign reg_2_spare = status_regs[2][7:5];
wire [7:0] TLU_TRIGGER_LOW_TIME_OUT;
assign TLU_TRIGGER_LOW_TIME_OUT = status_regs[3];

always @(posedge BUS_CLK)
begin
    if(RST)
    begin
        status_regs[0] <= 0;
        status_regs[1] <= 8'b0000_0000;
        status_regs[2] <= 8'd0; // 0: 32 clock cycles
        status_regs[3] <= 8'd0;
        status_regs[4] <= 0;
        status_regs[5] <= 0;
        status_regs[6] <= 0;
        status_regs[7] <= 0;
    end
    else if(BUS_WR && BUS_ADD < 8)
    begin
        status_regs[BUS_ADD[2:0]] <= BUS_DATA_IN;
    end
end

// read reg
reg [31:0] CURRENT_TRIGGER_NUMBER;
reg [31:0] CURRENT_TRIGGER_NUMBER_BUF;

always @ (negedge BUS_CLK)
begin
    BUS_DATA_OUT <= 0;
	 
    if (BUS_ADD == 4)
        BUS_DATA_OUT <= CURRENT_TRIGGER_NUMBER_BUF[7:0];
    else if (BUS_ADD == 5)
        BUS_DATA_OUT <= CURRENT_TRIGGER_NUMBER_BUF[15:8];
    else if (BUS_ADD == 6)
        BUS_DATA_OUT <= CURRENT_TRIGGER_NUMBER_BUF[23:16];
    else if (BUS_ADD == 7)
        BUS_DATA_OUT <= CURRENT_TRIGGER_NUMBER_BUF[31:24];
    else if(BUS_ADD < 4)
        BUS_DATA_OUT <= status_regs[BUS_ADD[2:0]]; // BUG AR 20391: use synchronous logic
end

//always @(*)
//begin
//    BUS_DATA_OUT = 0;
//	 
//    if (BUS_ADD == 4)
//        BUS_DATA_OUT = CURRENT_TRIGGER_NUMBER_BUF[7:0];
//    else if (BUS_ADD == 5)
//        BUS_DATA_OUT = CURRENT_TRIGGER_NUMBER_BUF[15:8];
//    else if (BUS_ADD == 6)
//        BUS_DATA_OUT = CURRENT_TRIGGER_NUMBER_BUF[23:16];
//    else if (BUS_ADD == 7)
//        BUS_DATA_OUT = CURRENT_TRIGGER_NUMBER_BUF[31:24];
//    else if(BUS_ADD < 4)
//        BUS_DATA_OUT = status_regs[BUS_ADD[2:0]]; // BUG AR 20391
//    
////    if(BUS_ADD == 1)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 2)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 3)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 4)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 5)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 6)
////        BUS_DATA_OUT = {8'b0};
////    else if(BUS_ADD == 7)
////        BUS_DATA_OUT = {8'b0};
//end

//assign some_value = (BUS_ADD==x && BUS_WR);
//assign some_value = status_regs[x]; // single reg
//assign some_value = {status_regs[x], status_regs[y]}; // multiple regs, specific order
//assign some_value = {status_regs[x:y]}; // multiple regs
//assign some_value = {status_regs[x][y]}; // single bit
//assign some_value = {status_regs[x][y:z]}; // multiple bits

// FIXME: temporary assigned here to make TLU running
reg TLU_DATA_SAVED_FLAG;
always @ (posedge BUS_CLK)
begin
    if (RST)
    begin
        CURRENT_TRIGGER_NUMBER <= 32'b0;
        TLU_DATA_SAVED_FLAG <= 1'b0;
    end
    else
    begin
        if (TLU_DATA_SAVE_FLAG == 1'b1)
        begin
            CURRENT_TRIGGER_NUMBER <= TLU_DATA[31:0];
            TLU_DATA_SAVED_FLAG <= 1'b1;
        end
        else
        begin
            CURRENT_TRIGGER_NUMBER <= CURRENT_TRIGGER_NUMBER;
            TLU_DATA_SAVED_FLAG <= 1'b0;
        end
    end
end

always @ (posedge BUS_CLK) // negedge 
begin
    if (RST)
        CURRENT_TRIGGER_NUMBER_BUF <= 32'b0;
    else
    begin
        if (BUS_ADD == 4)
            CURRENT_TRIGGER_NUMBER_BUF <= CURRENT_TRIGGER_NUMBER;
        else
            CURRENT_TRIGGER_NUMBER_BUF <= CURRENT_TRIGGER_NUMBER_BUF;
    end
end

wire                TLU_CLOCK_ENABLE;
wire                TLU_ASSERT_VETO;
wire                TLU_DEASSERT_VETO;
wire                TLU_RECEIVE_DATA_FLAG;
wire                TLU_RECEIVE_DATA_FLAG_CLK_5;
wire                TLU_DATA_RECEIVED_FLAG;

wire    [30:0]      TLU_DATA_CLK_5;
wire                TLU_DATA_SAVE_SIGNAL_CLK_5;
wire                TLU_DATA_SAVED_FLAG_CLK_5;
wire                TLU_DATA_SAVE_FLAG_CLK_5;
wire                TLU_TRIGGER_FLAG_CLK_40;
wire                TLU_TRIGGER_BUSY_CLK_40;
wire                TLU_TRIGGER_BUSY_CLK_160;
wire                TLU_TRIGGER_DONE_CLK_40;

reg tlu_clock_enable_negedge;
always @ (negedge CLK_5)
    tlu_clock_enable_negedge <= TLU_CLOCK_ENABLE;

// TLU clock
OFDDRCPE OFDDRCPE_TRIGGER_CLOCK (
    .CE((TLU_TRIGGER_CLOCK_INVERT==1'b1)? TLU_CLOCK_ENABLE : tlu_clock_enable_negedge),
    .C0(CLK_5),
    .C1(~CLK_5),
    .D0((TLU_TRIGGER_CLOCK_INVERT==1'b1)? 1'b0 : 1'b1), // normal: 1'b0
    .D1((TLU_TRIGGER_CLOCK_INVERT==1'b1)? 1'b1 : 1'b0), // normal: 1'b1
    .PRE(TLU_ASSERT_VETO),
    .CLR(TLU_DEASSERT_VETO),
    .Q(TLU_CLOCK)
);

// Trigger input port select
always @ (*)
begin
    if (RST)
        RJ45_ENABLED = 1'b0;
    else
    begin
        if ((RJ45_TRIGGER && RJ45_RESET && !RJ45_ENABLED) || TLU_MODE == 2'b00)
            RJ45_ENABLED = 1'b0;
        else
            RJ45_ENABLED = 1'b1;
    end
end

wire TLU_TRIGGER, TLU_RESET;
assign TLU_TRIGGER = (RJ45_ENABLED == 1'b1) ? RJ45_TRIGGER : LEMO_TRIGGER; // RJ45 inputs tied to 1 if no connector is plugged in
assign TLU_RESET = (RJ45_ENABLED == 1'b1) ? RJ45_RESET : LEMO_RESET; // RJ45 inputs tied to 1 if no connector is plugged in

wire TLU_TRIGGER_CLK_160, TLU_TRIGGER_FLAG_CLK_160, TLU_TRIGGER_CLK_40, TLU_TRIGGER_DISABLE;
reg TLU_TRIGGER_CLK_160_FF;

three_stage_synchronizer three_stage_tlu_trigger_synchronizer_CLK_160 (
    .CLK(CLK_160),
    .IN(TLU_TRIGGER),
    .OUT(TLU_TRIGGER_CLK_160)
);

three_stage_synchronizer three_stage_tlu_trigger_synchronizer_CLK_40 (
    .CLK(CLK_40),
    .IN(TLU_TRIGGER),
    .OUT(TLU_TRIGGER_CLK_40)
);

always @ (posedge CLK_160)
    TLU_TRIGGER_CLK_160_FF <= TLU_TRIGGER_CLK_160;

assign TLU_TRIGGER_FLAG_CLK_160 = ~TLU_TRIGGER_CLK_160_FF && TLU_TRIGGER_CLK_160;

wire TLU_TRIGGER_DISABLE_CLK_160;
three_stage_synchronizer three_stage_tlu_trigger_disable_synchronizer_CLK_40 (
    .CLK(CLK_160),
    .IN(TLU_TRIGGER_DISABLE),
    .OUT(TLU_TRIGGER_DISABLE_CLK_160)
);

task_domain_crossing tlu_trigger_flag_domain_crossing (
    .CLK_A(CLK_160),
    .CLK_B(CLK_40),
    .FLAG_IN_CLK_A(TLU_TRIGGER_FLAG_CLK_160),
    .FLAG_OUT_CLK_B(TLU_TRIGGER_FLAG_CLK_40),
    .BUSY_CLK_A(TLU_TRIGGER_BUSY_CLK_160),
    .BUSY_CLK_B(),
    .TASK_DONE_CLK_A(),
    .TASK_DONE_CLK_B(TLU_TRIGGER_DONE_CLK_40),
    .DISABLE_CLK_A(TLU_TRIGGER_DISABLE_CLK_160)
);

three_stage_synchronizer tlu_trigger_busy_synchronizer (
    .CLK(CLK_40),
    .IN(TLU_TRIGGER_BUSY_CLK_160),
    .OUT(TLU_TRIGGER_BUSY_CLK_40)
);

wire TLU_RESET_CLK_160;
three_stage_synchronizer three_tlu_reset_synchronizer (
    .CLK(CLK_160),
    .IN(TLU_RESET),
    .OUT(TLU_RESET_CLK_160)
);

reg TLU_RESET_CLK_160_FF;
wire TLU_RESET_FLAG_CLK_160;

always @ (posedge CLK_160)
    TLU_RESET_CLK_160_FF <= TLU_RESET_CLK_160;

assign TLU_RESET_FLAG_CLK_160 = ~TLU_RESET_CLK_160_FF && TLU_RESET_CLK_160;

flag_domain_crossing tlu_reset_flag_domain_crossing (
    .CLK_A(CLK_160),
    .CLK_B(CLK_40),
    .FLAG_IN_CLK_A(TLU_RESET_FLAG_CLK_160),
    .FLAG_OUT_CLK_B(TLU_RESET_FLAG)
);

wire [7:0] TLU_TRIGGER_LOW_TIME_OUT_CLK_40;
three_stage_synchronizer #(
    .WIDTH(8)
) tlu_trigger_low_timeout_sync (
    .CLK(CLK_40),
    .IN(TLU_TRIGGER_LOW_TIME_OUT),
    .OUT(TLU_TRIGGER_LOW_TIME_OUT_CLK_40)
);

wire [1:0] TLU_MODE_CLK_40;
three_stage_synchronizer #(
    .WIDTH(2)
) tlu_mode_sync (
    .CLK(CLK_40),
    .IN(TLU_MODE),
    .OUT(TLU_MODE_CLK_40)
);

tlu_controller_fsm tlu_controller_fsm_module (
    .RESET(RST),
    .CLK(CLK_40),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    
    .TLU_TRIGGER(TLU_TRIGGER_CLK_40),
    .TLU_TRIGGER_FLAG(TLU_TRIGGER_FLAG_CLK_40),
    .TLU_TRIGGER_BUSY(TLU_TRIGGER_BUSY_CLK_40),
    .TLU_TRIGGER_DONE(TLU_TRIGGER_DONE_CLK_40),
    
    .TLU_MODE(TLU_MODE_CLK_40),
    .TLU_BUSY(TLU_BUSY),
    .TLU_ASSERT_VETO(TLU_ASSERT_VETO),
    .TLU_DEASSERT_VETO(TLU_DEASSERT_VETO),
    .TLU_RECEIVE_DATA_FLAG(TLU_RECEIVE_DATA_FLAG),
    .TLU_DATA_RECEIVED_FLAG(TLU_DATA_RECEIVED_FLAG),
    .TLU_TRIGGER_LOW_TIME_OUT(TLU_TRIGGER_LOW_TIME_OUT_CLK_40),
    .TLU_TRIGGER_ABORT(TLU_TRIGGER_ABORT),
    .TLU_TRIGGER_DISABLE(TLU_TRIGGER_DISABLE),
    
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL)
    
//  output reg  [2:0]   state,
//  output reg  [2:0]   next
);


wire TLU_DATA_RECEIVED_FLAG_CLK_5;
task_domain_crossing tlu_trigger_data_flag_domain_crossing (
    .CLK_A(CLK_40),
    .CLK_B(CLK_5),
    .FLAG_IN_CLK_A(TLU_RECEIVE_DATA_FLAG),
    .FLAG_OUT_CLK_B(TLU_RECEIVE_DATA_FLAG_CLK_5),
    .BUSY_CLK_A(),
    .BUSY_CLK_B(),
    .TASK_DONE_CLK_A(TLU_DATA_RECEIVED_FLAG),
    .TASK_DONE_CLK_B(TLU_DATA_RECEIVED_FLAG_CLK_5),
    .DISABLE_CLK_A(1'b0)
);

wire [4:0] TLU_TRIGGER_CLOCK_CYCLES_CLK_5;
three_stage_synchronizer #(
    .WIDTH(5)
) tlu_trigger_clock_cycles_sync (
    .CLK(CLK_5),
    .IN(TLU_TRIGGER_CLOCK_CYCLES),
    .OUT(TLU_TRIGGER_CLOCK_CYCLES_CLK_5)
);

wire [3:0] TLU_TRIGGER_DATA_DELAY_CLK_5;
three_stage_synchronizer #(
    .WIDTH(4)
) tlu_trigger_data_delay_sync (
    .CLK(CLK_5),
    .IN(TLU_TRIGGER_DATA_DELAY),
    .OUT(TLU_TRIGGER_DATA_DELAY_CLK_5)
);

wire TLU_TRIGGER_DATA_MSB_FIRST_CLK_5;
three_stage_synchronizer tlu_trigger_data_msb_first_sync (
    .CLK(CLK_5),
    .IN(TLU_TRIGGER_DATA_MSB_FIRST),
    .OUT(TLU_TRIGGER_DATA_MSB_FIRST_CLK_5)
);

wire TLU_TRIGGER_CLK_5;
three_stage_synchronizer tlu_trigger_sync (
    .CLK(CLK_5),
    .IN(TLU_TRIGGER),
    .OUT(TLU_TRIGGER_CLK_5)
);

tlu_serial_to_parallel_fsm tlu_serial_to_parallel_fsm_module (
    .RESET(RST),
    .CLK(CLK_5),
    
    .TLU_TRIGGER_CLOCK_CYCLES(TLU_TRIGGER_CLOCK_CYCLES_CLK_5),
    .TLU_TRIGGER_DATA_DELAY(TLU_TRIGGER_DATA_DELAY_CLK_5),
    .TLU_TRIGGER_DATA_MSB_FIRST(TLU_TRIGGER_DATA_MSB_FIRST_CLK_5),
    
    .TLU_TRIGGER(TLU_TRIGGER_CLK_5),
    .TLU_RECEIVE_DATA_FLAG(TLU_RECEIVE_DATA_FLAG_CLK_5),
    .TLU_CLOCK_ENABLE(TLU_CLOCK_ENABLE),
    .TLU_DATA_RECEIVED_FLAG(TLU_DATA_RECEIVED_FLAG_CLK_5),
    
    .TLU_DATA(TLU_DATA_CLK_5),
    .TLU_DATA_SAVE_SIGNAL(TLU_DATA_SAVE_SIGNAL_CLK_5),
    .TLU_DATA_SAVE_FLAG(TLU_DATA_SAVE_FLAG_CLK_5),
    .TLU_DATA_SAVED_FLAG(TLU_DATA_SAVED_FLAG_CLK_5)
);

three_stage_synchronizer #(
    .WIDTH(32)
) tlu_data_sync (
    .CLK(BUS_CLK),
    .IN(TLU_DATA_CLK_5),
    .OUT(TLU_DATA)
);
//assign TLU_DATA = TLU_DATA_CLK_5;

three_stage_synchronizer tlu_data_signal_sync (
    .CLK(BUS_CLK),
    .IN(TLU_DATA_SAVE_SIGNAL_CLK_5),
    .OUT(TLU_DATA_SAVE_SIGNAL)
);

task_domain_crossing tlu_trigger_data_save_flag_domain_crossing (
    .CLK_A(CLK_5),
    .CLK_B(BUS_CLK),
    .FLAG_IN_CLK_A(TLU_DATA_SAVE_FLAG_CLK_5),
    .FLAG_OUT_CLK_B(TLU_DATA_SAVE_FLAG),
    .BUSY_CLK_A(),
    .BUSY_CLK_B(),
    .TASK_DONE_CLK_A(TLU_DATA_SAVED_FLAG_CLK_5),
    .TASK_DONE_CLK_B(TLU_DATA_SAVED_FLAG),
    .DISABLE_CLK_A(1'b0)
);

endmodule
