`timescale 1ps / 1ps
`default_nettype none

module top (
    
    input wire FCLK_IN, 
    
    //full speed 
    inout wire [7:0] DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FD,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //debug
    output wire [15:0] DEBUG_D,
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
        
    input FE_RX,
    
    input wire [3:0] LEMO_RX,
    output wire [3:0] TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,
    
    output CMD_CLK,
    output CMD_DATA,
    output POWER_EN_VD1
    
    //input wire FPGA_BUTTON // switch S2 on MultiIO board, active low
);

wire BUS_RST;
wire BUS_CLK;
wire BUS_CLK270;
wire CLK_40;
wire CLK_160;
wire CLK_5;
wire CLK_LOCKED;

assign POWER_EN_VD1 = 1'b1;
assign DEBUG_D = 16'ha5a5;

// 1Hz CLK
wire CE_1HZ; // use for sequential logic
wire CLK_1HZ; // don't connect to clock input, only combinatorial logic

clock_divider #(
    .DIVISOR(40000000)
) clock_divisor_40MHz_to_1Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE_1HZ(CE_1HZ),
    .CLK_1HZ(CLK_1HZ)
);

// Trigger
wire CMD_EXT_START_FLAG;
wire CMD_EXT_START_ENABLE;

wire LEMO_TRIGGER, LEMO_RESET;
assign LEMO_TRIGGER = LEMO_RX[0];
assign LEMO_RESET = LEMO_RX[1];
//assign ... = LEMO_RX[2];

// TLU
wire            RJ45_ENABLED;
wire            TLU_BUSY;                   // busy signal to TLU to deassert trigger
wire            TLU_CLOCK;
wire            CMD_READY;

wire            TLU_DATA_SAVE_SIGNAL;   // TLU trigger parallel data flag synchronized to XCK
wire            TLU_DATA_SAVE_FLAG;
wire            TLU_DATA_SAVED_FLAG;
wire    [31:0]  TLU_DATA_WITH_HEADER;   // TLU trigger parallel data synchronized to XCK
wire    [31:0]  TLU_DATA;

assign TLU_DATA_WITH_HEADER = {1'b1, TLU_DATA[30:0]}; // MSB always 1 to identify TLU trigger number

assign TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign TX[1] = TLU_BUSY; // in TLU handshake mode TLU_BUSY signal; also connected to RJ45 output
assign TX[2] = 1'b0;

// LED
parameter VERSION = 1; // all on: 31

wire RX_READY;
wire FIFO_NOT_EMPTY; // raised, when attempting to write to FIFO when it is full
wire FIFO_READ_ERROR; // raised, when attempting to read from FIFO when it is empty

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
assign LED1 = SHOW_VERSION? VERSION[0] : CLK_1HZ & CLK_LOCKED;
assign LED2 = SHOW_VERSION? VERSION[1] : RX_READY;
assign LED3 = SHOW_VERSION? VERSION[2] : FIFO_NOT_EMPTY;
assign LED4 = SHOW_VERSION? VERSION[3] : FIFO_READ_ERROR;
assign LED5 = SHOW_VERSION? VERSION[4] : RJ45_ENABLED;

reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

clk_gen iclkgen(
    .CLKIN(FCLK_IN),
    .CLKINBUF(BUS_CLK),
    .CLKINBUF270(BUS_CLK270),
    .CLKOUT160(CLK_160),
    .CLKOUT40(CLK_40),
    .CLKOUT5(CLK_5),
    .LOCKED(CLK_LOCKED)
);

wire [7:0] BUS_DATA_IN;
assign BUS_DATA_IN = DATA;

reg [7:0] DATA_OUT;

reg [15:0] CMD_ADD;
wire [7:0] CMD_BUS_DATA_OUT;
reg CMD_BUS_RD, CMD_BUS_WR;

reg [15:0] RX_ADD;
wire [7:0] RX_BUS_DATA_OUT;
reg RX_BUS_RD, RX_BUS_WR;

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
    
    RX_BUS_RD = 0;
    RX_BUS_WR = 0;
    RX_ADD = 0;
    
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
    else if( ADD_REAL < 16'h8100 ) begin
        RX_BUS_RD = ~RD_B;
        RX_BUS_WR = ~WR_B;
        RX_ADD = ADD_REAL-16'h8000;
        DATA_OUT = RX_BUS_DATA_OUT;
    end
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
    .CMD_READY(CMD_READY)
); 


wire FIFO_READ, FIFO_EMPTY;
wire [31:0] FIFO_DATA;
assign FIFO_DATA[31:24] = 8'b0;

fei4_rx ifei4_rx(
    .RX_CLK(CLK_160),
    .RX_CLK_LOCKED(CLK_LOCKED),
    .RX_DATA(FE_RX),
    
    .RX_READY(RX_READY),
     
    .FIFO_READ(FIFO_READ),
    .FIFO_EMPTY(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA[23:0]),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR),
    .BUS_RD(RX_BUS_RD)
);

wire USB_READ;
assign USB_READ = FREAD && FSTROBE;
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
    .USB_DATA(FD),
    
    .FIFO_READ_NEXT_OUT(FIFO_READ),
    .FIFO_EMPTY_IN(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA),
    
    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);


tlu_controller tlu_controller_module (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(TLU_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_RD(TLU_RD),
    .BUS_WR(TLU_WR),
    .BUS_DATA_OUT(TLU_BUS_DATA_OUT),
    
    .CLK_160(CLK_160),
    .CLK_40(CLK_40),
    .CLK_5(CLK_5),
    
    .RJ45_TRIGGER(RJ45_TRIGGER),
    .LEMO_TRIGGER(LEMO_TRIGGER),
    .RJ45_RESET(RJ45_RESET),
    .LEMO_RESET(LEMO_RESET),
    .RJ45_ENABLED(RJ45_ENABLED),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    .TLU_RESET_FLAG(),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    
    .TLU_DATA_SAVE_SIGNAL(TLU_DATA_SAVE_SIGNAL),
    .TLU_DATA_SAVE_FLAG(TLU_DATA_SAVE_FLAG),
    // FIXME: temporary assigned internally to make TLU running
    //.TLU_DATA_SAVED_FLAG(TLU_DATA_SAVED_FLAG),
    .TLU_DATA(TLU_DATA),
    .TLU_TRIGGER_ABORT(),

    .FIFO_NEAR_FULL(1'b0)
);


`ifdef SYNTHESIS_NOT
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
); 

chipscope_ila ichipscope_ila 
(
    .CONTROL(control_bus),
    .CLK(BUS_CLK), 
    .TRIG0({ADD_REAL, BUS_DATA_IN, TLU_WR, TLU_RD, WR_B, RD_B})
    //.CLK(CLK_160), 
    //.TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, FE_RX ,WR_B, RD_B})
        
); 
`endif


endmodule
