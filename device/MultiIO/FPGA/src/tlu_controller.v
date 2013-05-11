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
    
    input wire                  CMD_CLK,
    input wire                  TLU_CLK,
    
    input wire                  FIFO_READ,
    output reg                  FIFO_EMPTY,
    output reg      [31:0]      FIFO_DATA,
    
    input wire                  RJ45_TRIGGER,
    input wire                  LEMO_TRIGGER,
    input wire                  RJ45_RESET,
    input wire                  LEMO_RESET,
    output reg                  RJ45_ENABLED,
    output wire                 TLU_BUSY,
    output wire                 TLU_CLOCK,
    //output wire                 TLU_RESET_FLAG,
    
    input wire                  CMD_READY,
    output wire                 CMD_EXT_START_FLAG,
    input wire                  CMD_EXT_START_ENABLE,
    
    output wire                 TLU_DATA_SAVE_SIGNAL,
    output wire                 TLU_DATA_SAVE_FLAG,
    // FIXME: temporary assigned internally to make TLU running
    //input wire                  TLU_DATA_SAVED_FLAG,
    output wire     [31:0]      TLU_DATA,              // TLU trigger parallel data
    output wire                 TLU_TRIGGER_LOW_TIMEOUT_ERROR,
    output wire                 TLU_TRIGGER_ACCEPT_ERROR,
    output wire                 TLU_TRIGGER_ACCEPTED,
    
    input wire                  FIFO_NEAR_FULL
);

wire [31:0] TLU_DATA_BUS_CLK;
assign TLU_DATA = TLU_DATA_BUS_CLK;
wire TLU_DATA_SAVE_SIGNAL_BUS_CLK;
assign TLU_DATA_SAVE_SIGNAL = TLU_DATA_SAVE_SIGNAL_BUS_CLK;
wire TLU_DATA_SAVE_FLAG_BUS_CLK;
assign TLU_DATA_SAVE_FLAG = TLU_DATA_SAVE_FLAG_BUS_CLK;
wire TLU_TRIGGER_LOW_TIMEOUT_ERROR_BUS_CLK;
assign TLU_TRIGGER_LOW_TIMEOUT_ERROR = TLU_TRIGGER_LOW_TIMEOUT_ERROR_BUS_CLK;
wire TLU_TRIGGER_ACCEPT_ERROR_BUS_CLK;
assign TLU_TRIGGER_ACCEPT_ERROR = TLU_TRIGGER_ACCEPT_ERROR_BUS_CLK;
wire TLU_TRIGGER_ACCEPTED_BUS_CLK;
assign TLU_TRIGGER_ACCEPTED = TLU_TRIGGER_ACCEPTED_BUS_CLK;

//wire TLU_DATA_SAVED_FLAG_BUS_CLK;
//assign TLU_DATA_SAVED_FLAG_BUS_CLK = TLU_DATA_SAVED_FLAG;

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
    //BUS_DATA_OUT <= 0;
	 
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
    else
        BUS_DATA_OUT <= 0;
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
reg TLU_DATA_SAVED_FLAG_BUS_CLK;
always @ (posedge BUS_CLK)
begin
    if (RST)
    begin
        CURRENT_TRIGGER_NUMBER <= 32'b0;
        //TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b0;
    end
    else
    begin
        if (TLU_DATA_SAVE_FLAG_BUS_CLK == 1'b1)
        begin
            CURRENT_TRIGGER_NUMBER <= TLU_DATA_BUS_CLK[31:0];
            //TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b1;
        end
        else
        begin
            CURRENT_TRIGGER_NUMBER <= CURRENT_TRIGGER_NUMBER;
            //TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b0;
        end
    end
end

always @ (posedge BUS_CLK)
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
wire                TLU_RECEIVE_DATA_FLAG_BUS_CLK;
wire                TLU_RECEIVE_DATA_FLAG_TLU_CLK;
wire                TLU_DATA_RECEIVED_FLAG_BUS_CLK;

wire    [30:0]      TLU_DATA_TLU_CLK;
wire                TLU_DATA_SAVE_SIGNAL_TLU_CLK;
wire                TLU_DATA_SAVED_FLAG_TLU_CLK;
wire                TLU_DATA_SAVE_FLAG_TLU_CLK;
wire                TLU_TRIGGER_FLAG_BUS_CLK;
wire                TLU_RESET_FLAG_BUS_CLK;
//wire                TLU_TRIGGER_BUSY_BUS_CLK;
//wire                TLU_TRIGGER_DONE_BUS_CLK;

reg tlu_clock_enable_negedge;
always @ (negedge TLU_CLK)
    tlu_clock_enable_negedge <= TLU_CLOCK_ENABLE;

// TLU clock
OFDDRCPE OFDDRCPE_TRIGGER_CLOCK (
    .CE((TLU_TRIGGER_CLOCK_INVERT==1'b1)? TLU_CLOCK_ENABLE : tlu_clock_enable_negedge),
    .C0(TLU_CLK),
    .C1(~TLU_CLK),
    .D0((TLU_TRIGGER_CLOCK_INVERT==1'b1)? 1'b0 : 1'b1), // normal: 1'b0
    .D1((TLU_TRIGGER_CLOCK_INVERT==1'b1)? 1'b1 : 1'b0), // normal: 1'b1
    .PRE(TLU_ASSERT_VETO),
    .CLR(TLU_DEASSERT_VETO),
    .Q(TLU_CLOCK)
);

// Trigger input port select
wire RJ45_TRIGGER_BUS_CLK, LEMO_TRIGGER_BUS_CLK, RJ45_RESET_BUS_CLK, LEMO_RESET_BUS_CLK;

always @ (posedge BUS_CLK)
begin
    if (RST)
        RJ45_ENABLED <= 1'b0;
    else
    begin
        if ((RJ45_TRIGGER_BUS_CLK && RJ45_RESET_BUS_CLK && !RJ45_ENABLED) || TLU_MODE == 2'b00)
            RJ45_ENABLED <= 1'b0;
        else
            RJ45_ENABLED <= 1'b1;
    end
end

three_stage_synchronizer three_stage_rj45_trigger_synchronizer_bus_clk (
    .CLK(BUS_CLK),
    .IN(RJ45_TRIGGER),
    .OUT(RJ45_TRIGGER_BUS_CLK)
);

three_stage_synchronizer three_stage_lemo_trigger_synchronizer_bus_clk (
    .CLK(BUS_CLK),
    .IN(LEMO_TRIGGER),
    .OUT(LEMO_TRIGGER_BUS_CLK)
);

three_stage_synchronizer three_stage_rj45_reset_synchronizer_bus_clk (
    .CLK(BUS_CLK),
    .IN(RJ45_RESET),
    .OUT(RJ45_RESET_BUS_CLK)
);

three_stage_synchronizer three_stage_lemo_reset_synchronizer_bus_clk (
    .CLK(BUS_CLK),
    .IN(LEMO_RESET),
    .OUT(LEMO_RESET_BUS_CLK)
);

wire TLU_TRIGGER_BUS_CLK, TLU_RESET_BUS_CLK;
assign TLU_TRIGGER_BUS_CLK = (RJ45_ENABLED == 1'b1) ? RJ45_TRIGGER_BUS_CLK : LEMO_TRIGGER_BUS_CLK; // RJ45 inputs tied to 1 if no connector is plugged in
assign TLU_RESET_BUS_CLK = (RJ45_ENABLED == 1'b1) ? RJ45_RESET_BUS_CLK : LEMO_RESET_BUS_CLK; // RJ45 inputs tied to 1 if no connector is plugged in

reg TLU_TRIGGER_BUS_CLK_FF;
always @ (posedge BUS_CLK)
    TLU_TRIGGER_BUS_CLK_FF <= TLU_TRIGGER_BUS_CLK;

assign TLU_TRIGGER_FLAG_BUS_CLK = ~TLU_TRIGGER_BUS_CLK_FF && TLU_TRIGGER_BUS_CLK;

reg TLU_RESET_BUS_CLK_FF;
always @ (posedge BUS_CLK)
    TLU_RESET_BUS_CLK_FF <= TLU_RESET_BUS_CLK;

assign TLU_RESET_FLAG_BUS_CLK = ~TLU_RESET_BUS_CLK_FF && TLU_RESET_BUS_CLK;

wire CMD_READY_BUS_CLK;
three_stage_synchronizer three_stage_cmd_ready_synchronizer (
    .CLK(BUS_CLK),
    .IN(CMD_READY),
    .OUT(CMD_READY_BUS_CLK)
);

wire CMD_EXT_START_FLAG_BUS_CLK;
flag_domain_crossing cmd_ext_start_flag_domain_crossing (
    .CLK_A(BUS_CLK),
    .CLK_B(CMD_CLK),
    .FLAG_IN_CLK_A(CMD_EXT_START_FLAG_BUS_CLK),
    .FLAG_OUT_CLK_B(CMD_EXT_START_FLAG)
);

wire CMD_EXT_START_ENABLE_BUS_CLK;
three_stage_synchronizer three_stage_cmd_external_start_synchronizer (
    .CLK(BUS_CLK),
    .IN(CMD_EXT_START_ENABLE),
    .OUT(CMD_EXT_START_ENABLE_BUS_CLK)
);

tlu_controller_fsm tlu_controller_fsm_module (
    .RESET(RST),
    .CLK(BUS_CLK),
    
    .CMD_READY(CMD_READY_BUS_CLK),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG_BUS_CLK),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE_BUS_CLK),
    
    .TLU_TRIGGER(TLU_TRIGGER_BUS_CLK),
    .TLU_TRIGGER_FLAG(TLU_TRIGGER_FLAG_BUS_CLK),
    // .TLU_TRIGGER_BUSY(TLU_TRIGGER_BUSY_BUS_CLK),
    // .TLU_TRIGGER_DONE(TLU_TRIGGER_DONE_BUS_CLK),
    
    .TLU_MODE(TLU_MODE), // from register
    .TLU_BUSY(TLU_BUSY),
    .TLU_ASSERT_VETO(TLU_ASSERT_VETO),
    .TLU_DEASSERT_VETO(TLU_DEASSERT_VETO),
    .TLU_RECEIVE_DATA_FLAG(TLU_RECEIVE_DATA_FLAG_BUS_CLK),
    .TLU_DATA_RECEIVED_FLAG(TLU_DATA_RECEIVED_FLAG_BUS_CLK),
    .TLU_TRIGGER_LOW_TIME_OUT(TLU_TRIGGER_LOW_TIME_OUT), // from register
    .TLU_TRIGGER_LOW_TIMEOUT_ERROR(TLU_TRIGGER_LOW_TIMEOUT_ERROR_BUS_CLK),
    .TLU_TRIGGER_ACCEPT_ERROR(TLU_TRIGGER_ACCEPT_ERROR_BUS_CLK),
    .TLU_TRIGGER_ACCEPTED(TLU_TRIGGER_ACCEPTED_BUS_CLK),
    
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL)
    
//  output reg  [2:0]   state,
//  output reg  [2:0]   next
);

// between tlu_controller_fsm and tlu_serial_to_parallel_fsm
wire TLU_DATA_RECEIVED_FLAG_TLU_CLK;
task_domain_crossing tlu_trigger_data_flag_domain_crossing (
    .CLK_A(BUS_CLK),
    .CLK_B(TLU_CLK),
    .FLAG_IN_CLK_A(TLU_RECEIVE_DATA_FLAG_BUS_CLK),
    .FLAG_OUT_CLK_B(TLU_RECEIVE_DATA_FLAG_TLU_CLK),
    .BUSY_CLK_A(),
    .BUSY_CLK_B(),
    .TASK_DONE_CLK_A(TLU_DATA_RECEIVED_FLAG_BUS_CLK),
    .TASK_DONE_CLK_B(TLU_DATA_RECEIVED_FLAG_TLU_CLK)
);

wire [4:0] TLU_TRIGGER_CLOCK_CYCLES_TLU_CLK;
three_stage_synchronizer #(
    .WIDTH(5)
) tlu_trigger_clock_cycles_sync (
    .CLK(TLU_CLK),
    .IN(TLU_TRIGGER_CLOCK_CYCLES),
    .OUT(TLU_TRIGGER_CLOCK_CYCLES_TLU_CLK)
);

wire [3:0] TLU_TRIGGER_DATA_DELAY_TLU_CLK;
three_stage_synchronizer #(
    .WIDTH(4)
) tlu_trigger_data_delay_sync (
    .CLK(TLU_CLK),
    .IN(TLU_TRIGGER_DATA_DELAY),
    .OUT(TLU_TRIGGER_DATA_DELAY_TLU_CLK)
);

wire TLU_TRIGGER_DATA_MSB_FIRST_TLU_CLK;
three_stage_synchronizer tlu_trigger_data_msb_first_sync (
    .CLK(TLU_CLK),
    .IN(TLU_TRIGGER_DATA_MSB_FIRST),
    .OUT(TLU_TRIGGER_DATA_MSB_FIRST_TLU_CLK)
);

wire TLU_TRIGGER_TLU_CLK;
three_stage_synchronizer tlu_trigger_sync (
    .CLK(TLU_CLK),
    .IN(RJ45_TRIGGER), // take TLU trigger number only from RJ45
    .OUT(TLU_TRIGGER_TLU_CLK)
);

tlu_serial_to_parallel_fsm tlu_serial_to_parallel_fsm_module (
    .RESET(RST),
    .CLK(TLU_CLK),
    
    .TLU_TRIGGER_CLOCK_CYCLES(TLU_TRIGGER_CLOCK_CYCLES_TLU_CLK),
    .TLU_TRIGGER_DATA_DELAY(TLU_TRIGGER_DATA_DELAY_TLU_CLK),
    .TLU_TRIGGER_DATA_MSB_FIRST(TLU_TRIGGER_DATA_MSB_FIRST_TLU_CLK),
    
    .TLU_TRIGGER(TLU_TRIGGER_TLU_CLK),
    .TLU_RECEIVE_DATA_FLAG(TLU_RECEIVE_DATA_FLAG_TLU_CLK),
    .TLU_CLOCK_ENABLE(TLU_CLOCK_ENABLE),
    .TLU_DATA_RECEIVED_FLAG(TLU_DATA_RECEIVED_FLAG_TLU_CLK),
    
    .TLU_DATA(TLU_DATA_TLU_CLK),
    .TLU_DATA_SAVE_SIGNAL(TLU_DATA_SAVE_SIGNAL_TLU_CLK),
    .TLU_DATA_SAVE_FLAG(TLU_DATA_SAVE_FLAG_TLU_CLK),
    .TLU_DATA_SAVED_FLAG(TLU_DATA_SAVED_FLAG_TLU_CLK)
);

three_stage_synchronizer #(
    .WIDTH(32)
) tlu_data_sync (
    .CLK(BUS_CLK),
    .IN(TLU_DATA_TLU_CLK),
    .OUT(TLU_DATA_BUS_CLK)
);

three_stage_synchronizer tlu_data_signal_sync (
    .CLK(BUS_CLK),
    .IN(TLU_DATA_SAVE_SIGNAL_TLU_CLK),
    .OUT(TLU_DATA_SAVE_SIGNAL_BUS_CLK)
);

task_domain_crossing tlu_trigger_data_save_flag_domain_crossing (
    .CLK_A(TLU_CLK),
    .CLK_B(BUS_CLK),
    .FLAG_IN_CLK_A(TLU_DATA_SAVE_FLAG_TLU_CLK),
    .FLAG_OUT_CLK_B(TLU_DATA_SAVE_FLAG_BUS_CLK),
    .BUSY_CLK_A(),
    .BUSY_CLK_B(),
    .TASK_DONE_CLK_A(TLU_DATA_SAVED_FLAG_TLU_CLK),
    .TASK_DONE_CLK_B(TLU_DATA_SAVED_FLAG_BUS_CLK)
);

// FIFO
//assign FIFO_DATA = {1'b1, TLU_TRIGGER_ACCEPT_ERROR, TLU_TRIGGER_LOW_TIMEOUT_ERROR, 14'b0, TLU_DATA_BUS_CLK[14:0]};
//do something with FIFO_READ
//assign FIFO_EMPTY = 1'b1;

// reg FIFO_READ_FF;
// always @ (posedge BUS_CLK)
    // FIFO_READ_FF <= FIFO_READ;

always @ (posedge BUS_CLK)
begin
    if (RST)
    begin
        FIFO_DATA <= 32'b0;
    end
    else
    begin
        if (TLU_DATA_SAVE_FLAG_BUS_CLK == 1'b1)
        begin
            FIFO_DATA <= {1'b1, TLU_TRIGGER_ACCEPT_ERROR, TLU_TRIGGER_LOW_TIMEOUT_ERROR, 14'b0, TLU_DATA_BUS_CLK[14:0]}; // header, 16-bit error code, 15-bit TLU trigger number 
        end
        else if (FIFO_READ == 1'b1)
        begin
            FIFO_DATA <= 32'b0;
        end
        else
        begin
            FIFO_DATA <= FIFO_DATA;
        end
    end
end

always @ (posedge BUS_CLK)
begin
    if (RST)
    begin
        FIFO_EMPTY <= 1'b1;
        TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b0;
    end
    else
    begin
        if (FIFO_READ == 1'b1)
        begin
            FIFO_EMPTY <= 1'b1;
            TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b1;
        end
        else if (TLU_DATA_SAVE_FLAG_BUS_CLK == 1'b1)
        begin
            FIFO_EMPTY <= 1'b0;
            TLU_DATA_SAVED_FLAG_BUS_CLK <= 1'b0;
        end
        else
        begin
            FIFO_EMPTY <= FIFO_EMPTY;
            TLU_DATA_SAVED_FLAG_BUS_CLK <= TLU_DATA_SAVED_FLAG_BUS_CLK;
        end
        
    end
end

endmodule
