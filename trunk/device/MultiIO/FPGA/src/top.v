`timescale 1ps / 1ps
`default_nettype none

module top (
    
    input wire FCLK_IN, // 48MHz
    
    //full speed 
    inout wire [7:0] DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FDATA,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //debug ports
    output wire [15:0] DEBUG_D,
    output wire [10:0] MULTI_IO, // Pin 1-11, 12: not connected, 13, 15: DGND, 14, 16: VCC_3.3V
    
    //LED
    output wire LED1,
    output wire LED2,
    output wire LED3,
    output wire LED4,
    output wire LED5,
    
    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,
    
    input wire [2:0] LEMO_RX,
    output wire [2:0] TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,
    
    output wire CMD_CLK,
    output wire CMD_DATA,
    output wire EN_V1, // EN_VA1 on SCC, EN_VDD1 on BIC
    output wire EN_V2, // EN_VA2 on SCC, EN_VDD2 on BIC
    output wire EN_V3, // EN_VD2 on SCC, EN_VDD3 on BIC
    output wire EN_V4, // EN_VD1 on SCC, EN_VDD4 on BIC
    
    input wire DOBOUT1, // BIC only
    input wire DOBOUT2, // BIC only
    input wire DOBOUT3, // BIC only
    input wire DOBOUT4, // DO on SCC
    
    // Over Current Protection (BIC only)
    input wire OC1,
    input wire OC2,
    input wire OC3,
    input wire OC4,
    
    // Select (SEL) LED (BIC only)
    output wire SEL1,
    output wire SEL2,
    output wire SEL3,
    output wire SEL4
    
    //input wire FPGA_BUTTON // switch S2 on MultiIO board, active low
);

wire BUS_RST;
wire BUS_CLK;
wire BUS_CLK270;
wire CLK_40;
wire RX_CLK;
wire RX_CLK90;
wire DATA_CLK;
wire CLK_LOCKED;

assign EN_V1 = 1'b1;
assign EN_V2 = 1'b1;
assign EN_V3 = 1'b1;
assign EN_V4 = 1'b1;

assign SEL1 = 1'b1;
assign SEL2 = 1'b1;
assign SEL3 = 1'b1;
assign SEL4 = 1'b1;

assign MULTI_IO = 11'b000_0000_0000;
assign DEBUG_D = 16'ha5a5;

// 1Hz CLK
wire CE_1HZ; // use for sequential logic
wire CLK_1HZ; // don't connect to clock input, only combinatorial logic
clock_divider #(
    .DIVISOR(40000000)
) clock_divisor_40MHz_to_1Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE(CE_1HZ),
    .CLOCK(CLK_1HZ)
);

wire CLK_2HZ;
clock_divider #(
    .DIVISOR(20000000)
) clock_divisor_40MHz_to_2Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_2HZ)
);

wire LEMO_TRIGGER, LEMO_RESET, EXT_VETO;
assign LEMO_TRIGGER = LEMO_RX[0];
assign LEMO_RESET = LEMO_RX[1];
assign EXT_VETO = LEMO_RX[2];

// TLU
wire            RJ45_ENABLED;
wire            TLU_BUSY;               // busy signal to TLU to deassert trigger
wire            TLU_CLOCK;

// CMD
wire            CMD_EXT_START_FLAG;     // to CMD FSM
wire            CMD_EXT_START_ENABLE;   // from CMD FSM
wire            CMD_READY;              // to TLU FSM
wire            CMD_START_FLAG;         // for triggering external devices
//reg             CMD_CAL;                // when CAL command is send

assign TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign TX[1] = TLU_BUSY | (CMD_START_FLAG/*CMD_CAL*/ & ~CMD_EXT_START_ENABLE); // TLU_BUSY signal; also connected to RJ45 output. Asserted when TLU FSM has accepted a trigger or when CMD FSM is busy. 
assign TX[2] = (RJ45_ENABLED == 1'b1) ? RJ45_TRIGGER : LEMO_TRIGGER;

// LED
parameter VERSION = 3; // all on: 31

wire RX_READY, RX_READY_4, RX_ERR_4, RX_READY_3, RX_ERR_3, RX_READY_2, RX_ERR_2, RX_READY_1, RX_ERR_1;
assign RX_READY = RX_READY_4 | RX_READY_3 | RX_READY_2 | RX_READY_1;
wire FIFO_NOT_EMPTY; // raised, when SRAM FIFO is not empty
wire FIFO_FULL; // raised, when SRAM FIFO is full
wire FIFO_READ_ERROR; // raised, when attempting to read from SRAM FIFO when it is empty
wire RX_FIFO_FULL, RX_FIFO_FULL_4, RX_FIFO_FULL_3, RX_FIFO_FULL_2, RX_FIFO_FULL_1; // raised, when RX FIFO full
assign RX_FIFO_FULL = RX_FIFO_FULL_4 | RX_FIFO_FULL_3 | RX_FIFO_FULL_2 | RX_FIFO_FULL_1;
reg FIFO_NEAR_FULL;
always @ (posedge BUS_CLK)
begin
    if (RX_READY == 1'b0 || FIFO_FULL == 1'b1 || RX_FIFO_FULL == 1'b1)
        FIFO_NEAR_FULL <= 1'b1;
    else
        FIFO_NEAR_FULL <= 1'b0;
end

wire SHOW_VERSION;

SRLC16E # (
    .INIT(16'hF000) // in seconds, MSB shifted first
) SRLC16E_LED (
    .Q(SHOW_VERSION),
    .Q15(),
    .A0(1'b1),
    .A1(1'b1),
    .A2(1'b1),
    .A3(1'b1),
    .CE(CE_1HZ),
    .CLK(CLK_40),
    .D(1'b0)
);

// LED assignments
assign LED1 = SHOW_VERSION? VERSION[0] : RJ45_ENABLED? (CLK_2HZ & CLK_LOCKED) : (CLK_1HZ & CLK_LOCKED);
assign LED2 = SHOW_VERSION? VERSION[1] : RX_READY_1 & (CLK_1HZ | ~RX_ERR_1); // blink when RX_ERR, off when no RX_READY, on when everything is OK
assign LED3 = SHOW_VERSION? VERSION[2] : RX_READY_2 & (CLK_1HZ | ~RX_ERR_2);//(FIFO_FULL == 1'b1 || RX_FIFO_FULL == 1'b1);
assign LED4 = SHOW_VERSION? VERSION[3] : RX_READY_3 & (CLK_1HZ | ~RX_ERR_3);//FIFO_READ_ERROR;
assign LED5 = SHOW_VERSION? VERSION[4] : RX_READY_4 & (CLK_1HZ | ~RX_ERR_4);//RJ45_ENABLED;

reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

clk_gen iclkgen(
    .U1_CLKIN_IN(FCLK_IN), 
    .U1_RST_IN(1'b0),  
    .U1_CLKIN_IBUFG_OUT(), 
    .U1_CLK0_OUT(BUS_CLK), 
    .U1_CLK270_OUT(BUS_CLK270), 
    .U1_STATUS_OUT(), 
    .U2_CLKFX_OUT(CLK_40),
    .U2_CLKDV_OUT(DATA_CLK),
    .U2_CLK0_OUT(RX_CLK), 
    .U2_CLK90_OUT(RX_CLK90),
    .U2_LOCKED_OUT(CLK_LOCKED),
    .U2_STATUS_OUT()
);

wire [7:0] BUS_DATA_IN;
assign BUS_DATA_IN = DATA;

reg [7:0] DATA_OUT;

reg [15:0] CMD_ADD;
wire [7:0] CMD_BUS_DATA_OUT;
reg CMD_BUS_RD, CMD_BUS_WR;

reg [15:0] RX_ADD_4;
wire [7:0] RX_BUS_DATA_OUT_4;
reg RX_BUS_RD_4, RX_BUS_WR_4;

reg [15:0] RX_ADD_3;
wire [7:0] RX_BUS_DATA_OUT_3;
reg RX_BUS_RD_3, RX_BUS_WR_3;

reg [15:0] RX_ADD_2;
wire [7:0] RX_BUS_DATA_OUT_2;
reg RX_BUS_RD_2, RX_BUS_WR_2;

reg [15:0] RX_ADD_1;
wire [7:0] RX_BUS_DATA_OUT_1;
reg RX_BUS_RD_1, RX_BUS_WR_1;

reg [15:0] FIFO_ADD;
wire [7:0] FIFO_BUS_DATA_OUT;
reg FIFO_RD, FIFO_WR;

reg [15:0] TLU_ADD;
wire [7:0] TLU_BUS_DATA_OUT;
reg TLU_RD, TLU_WR;

wire [15:0] ADD_REAL;
assign ADD_REAL = ADD - 16'h4000;

always@ (*) begin
    DATA_OUT = 0;
    
    CMD_ADD = 0;
    CMD_BUS_RD = 0;
    CMD_BUS_WR = 0;
    
    RX_BUS_RD_4 = 0;
    RX_BUS_WR_4 = 0;
    RX_ADD_4 = 0;
    
    RX_BUS_RD_3 = 0;
    RX_BUS_WR_3 = 0;
    RX_ADD_3 = 0;
    
    RX_BUS_RD_2 = 0;
    RX_BUS_WR_2 = 0;
    RX_ADD_2 = 0;
    
    RX_BUS_RD_1 = 0;
    RX_BUS_WR_1 = 0;
    RX_ADD_1 = 0;
    
    FIFO_ADD = 0;
    FIFO_RD = 0;
    FIFO_WR = 0;
    
    TLU_ADD = 0;
    TLU_RD = 0;
    TLU_WR = 0;
    
    if( ADD_REAL < 16'h8000 ) begin
        CMD_BUS_RD = ~RD_B;
        CMD_BUS_WR = ~WR_B;
        CMD_ADD = ADD_REAL;
        DATA_OUT = CMD_BUS_DATA_OUT;
    end
    // else if( ADD_REAL < 16'h8100 ) begin
        // RX_BUS_RD = ~RD_B;
        // RX_BUS_WR = ~WR_B;
        // RX_ADD = ADD_REAL-16'h8000;
        // DATA_OUT = RX_BUS_DATA_OUT;
    // end
    else if( ADD_REAL < 16'h8200 ) begin
        FIFO_RD = ~RD_B;
        FIFO_WR = ~WR_B;
        FIFO_ADD = ADD_REAL-16'h8100;
        DATA_OUT = FIFO_BUS_DATA_OUT;
    end
    else if( ADD_REAL < 16'h8300 ) begin
        TLU_RD = ~RD_B;
        TLU_WR = ~WR_B;
        TLU_ADD = ADD_REAL-16'h8200;
        DATA_OUT = TLU_BUS_DATA_OUT;
    end
    else if( ADD_REAL < 16'h8400 ) begin
        RX_BUS_RD_4 = ~RD_B;
        RX_BUS_WR_4 = ~WR_B;
        RX_ADD_4 = ADD_REAL-16'h8300;
        DATA_OUT = RX_BUS_DATA_OUT_4;
    end
    else if( ADD_REAL < 16'h8500 ) begin
        RX_BUS_RD_3 = ~RD_B;
        RX_BUS_WR_3 = ~WR_B;
        RX_ADD_3 = ADD_REAL-16'h8400;
        DATA_OUT = RX_BUS_DATA_OUT_3;
    end
    else if( ADD_REAL < 16'h8600 ) begin
        RX_BUS_RD_2 = ~RD_B;
        RX_BUS_WR_2 = ~WR_B;
        RX_ADD_2 = ADD_REAL-16'h8500;
        DATA_OUT = RX_BUS_DATA_OUT_2;
    end
    else if( ADD_REAL < 16'h8700 ) begin
        RX_BUS_RD_1 = ~RD_B;
        RX_BUS_WR_1 = ~WR_B;
        RX_ADD_1 = ADD_REAL-16'h8600;
        DATA_OUT = RX_BUS_DATA_OUT_1;
    end
end

assign DATA = ~RD_B ? DATA_OUT : 8'bzzzz_zzzz;

cmd_seq icmd
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(CMD_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(CMD_BUS_RD),
    .BUS_WR(CMD_BUS_WR),
    .BUS_DATA_OUT(CMD_BUS_DATA_OUT),
    
    .CMD_CLK_OUT(CMD_CLK),
    .CMD_CLK_IN(CLK_40),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    .CMD_DATA(CMD_DATA),
    .CMD_READY(CMD_READY),
    .CMD_START_FLAG(CMD_START_FLAG)
);

//Recognize CAL command for external device triggering
//reg [8:0] cmd_rx_reg;
//always@(posedge CMD_CLK)
//    cmd_rx_reg[8:0] <= {cmd_rx_reg[7:0],CMD_DATA};
//
//always@(posedge CMD_CLK)
//    CMD_CAL <= (cmd_rx_reg == 9'b101100100);

wire            FIFO_READ;
wire            FIFO_EMPTY;
wire    [31:0]  FIFO_DATA;

wire            FE_FIFO_READ_4;
wire            FE_FIFO_EMPTY_4;
wire    [31:0]  FE_FIFO_DATA_4;

wire            FE_FIFO_READ_3;
wire            FE_FIFO_EMPTY_3;
wire    [31:0]  FE_FIFO_DATA_3;

wire            FE_FIFO_READ_2;
wire            FE_FIFO_EMPTY_2;
wire    [31:0]  FE_FIFO_DATA_2;

wire            FE_FIFO_READ_1;
wire            FE_FIFO_EMPTY_1;
wire    [31:0]  FE_FIFO_DATA_1;

wire            TLU_FIFO_READ;
wire            TLU_FIFO_EMPTY;
wire    [31:0]  TLU_FIFO_DATA;

wire [3:0] FE_FIFO_REQ;
assign FE_FIFO_REQ = {~FE_FIFO_EMPTY_1, ~FE_FIFO_EMPTY_2, ~FE_FIFO_EMPTY_3, ~FE_FIFO_EMPTY_4};
wire TLU_FIFO_REQ;
assign TLU_FIFO_REQ = ~TLU_FIFO_EMPTY;
wire [4:0] FIFO_READ_SEL;

assign {FE_FIFO_READ_1, FE_FIFO_READ_2, FE_FIFO_READ_3, FE_FIFO_READ_4, TLU_FIFO_READ} = (FIFO_READ_SEL & ({5{FIFO_READ}}));
assign FIFO_EMPTY = ~((FIFO_READ_SEL & {FE_FIFO_REQ, TLU_FIFO_REQ}) != 5'b0_0000);
assign FIFO_DATA = (({32{FIFO_READ_SEL[4]}} & FE_FIFO_DATA_1) | ({32{FIFO_READ_SEL[3]}} & FE_FIFO_DATA_2) | ({32{FIFO_READ_SEL[2]}} & FE_FIFO_DATA_3) | ({32{FIFO_READ_SEL[1]}} & FE_FIFO_DATA_4) | ({32{FIFO_READ_SEL[0]}} & TLU_FIFO_DATA));

arbiter #(
    .WIDTH(5)
) arbiter_inst (
    .req({FE_FIFO_REQ, TLU_FIFO_REQ}),
    .grant(FIFO_READ_SEL),
    .base(5'b0_0001) // one hot, TLU has highest priority followed by higher indexed requests
);

wire USB_READ;
assign USB_READ = FREAD & FSTROBE;

out_fifo iout_fifo
(
    .BUS_CLK(BUS_CLK),
    .BUS_CLK270(BUS_CLK270),
    .BUS_RST(BUS_RST),
    .BUS_ADD(FIFO_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(FIFO_RD),
    .BUS_WR(FIFO_WR),
    .BUS_DATA_OUT(FIFO_BUS_DATA_OUT),
    
    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),
    
    .USB_READ(USB_READ),
    .USB_DATA(FDATA),
    
    .FIFO_READ_NEXT_OUT(FIFO_READ),
    .FIFO_EMPTY_IN(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA),
    
    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);

parameter DSIZE = 10;
//parameter CLKIN_PERIOD = 6.250;

fei4_rx #(
    .DSIZE(DSIZE),
    .DATA_IDENTIFIER(4)
) ifei4_rx_4 (
    .RX_CLK(RX_CLK),
    .RX_CLK90(RX_CLK90),
    .DATA_CLK(DATA_CLK),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(DOBOUT4),
    
    .RX_READY(RX_READY_4),
    .RX_ERR(RX_ERR_4),
     
    .FIFO_READ(FE_FIFO_READ_4),
    .FIFO_EMPTY(FE_FIFO_EMPTY_4),
    .FIFO_DATA(FE_FIFO_DATA_4),
    
    .RX_FIFO_FULL(RX_FIFO_FULL_4),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD_4),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT_4),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR_4),
    .BUS_RD(RX_BUS_RD_4)
);

fei4_rx #(
    .DSIZE(DSIZE),
    .DATA_IDENTIFIER(3)
) ifei4_rx_3 (
    .RX_CLK(RX_CLK),
    .RX_CLK90(RX_CLK90),
    .DATA_CLK(DATA_CLK),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(DOBOUT3),
    
    .RX_READY(RX_READY_3),
    .RX_ERR(RX_ERR_3),
     
    .FIFO_READ(FE_FIFO_READ_3),
    .FIFO_EMPTY(FE_FIFO_EMPTY_3),
    .FIFO_DATA(FE_FIFO_DATA_3),
    
    .RX_FIFO_FULL(RX_FIFO_FULL_3),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD_3),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT_3),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR_3),
    .BUS_RD(RX_BUS_RD_3)
);

fei4_rx #(
    .DSIZE(DSIZE),
    .DATA_IDENTIFIER(2)
) ifei4_rx_2 (
    .RX_CLK(RX_CLK),
    .RX_CLK90(RX_CLK90),
    .DATA_CLK(DATA_CLK),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(DOBOUT2),
    
    .RX_READY(RX_READY_2),
    .RX_ERR(RX_ERR_2),
     
    .FIFO_READ(FE_FIFO_READ_2),
    .FIFO_EMPTY(FE_FIFO_EMPTY_2),
    .FIFO_DATA(FE_FIFO_DATA_2),
    
    .RX_FIFO_FULL(RX_FIFO_FULL_2),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD_2),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT_2),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR_2),
    .BUS_RD(RX_BUS_RD_2)
);

fei4_rx #(
    .DSIZE(DSIZE),
    .DATA_IDENTIFIER(1)
) ifei4_rx_1 (
    .RX_CLK(RX_CLK),
    .RX_CLK90(RX_CLK90),
    .DATA_CLK(DATA_CLK),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(DOBOUT1),
    
    .RX_READY(RX_READY_1),
    .RX_ERR(RX_ERR_1),
     
    .FIFO_READ(FE_FIFO_READ_1),
    .FIFO_EMPTY(FE_FIFO_EMPTY_1),
    .FIFO_DATA(FE_FIFO_DATA_1),
    
    .RX_FIFO_FULL(RX_FIFO_FULL_1),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD_1),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT_1),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR_1),
    .BUS_RD(RX_BUS_RD_1)
);

tlu_controller #(
    .DIVISOR(12)
) tlu_controller_module (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(TLU_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(TLU_RD),
    .BUS_WR(TLU_WR),
    .BUS_DATA_OUT(TLU_BUS_DATA_OUT),
    
    .CMD_CLK(CLK_40),
    
    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),
    
    .RJ45_TRIGGER(RJ45_TRIGGER),
    .LEMO_TRIGGER(LEMO_TRIGGER),
    .RJ45_RESET(RJ45_RESET),
    .LEMO_RESET(LEMO_RESET),
    .RJ45_ENABLED(RJ45_ENABLED),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .EXT_VETO(EXT_VETO),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),

    .FIFO_NEAR_FULL(FIFO_NEAR_FULL)
);

// Chipscope
`ifdef SYNTHESIS_NOT
//`ifdef SYNTHESIS
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
);

chipscope_ila ichipscope_ila
(
    .CONTROL(control_bus),
    .CLK(CLK_160),
    .TRIG0({FIFO_DATA[23:0], TLU_BUSY, TLU_FIFO_EMPTY, TLU_FIFO_READ, FE_FIFO_EMPTY, FE_FIFO_READ, FIFO_EMPTY, FIFO_READ})
    //.CLK(CLK_160),
    //.TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, DOBOUT4 ,WR_B, RD_B})
);
`endif


endmodule
