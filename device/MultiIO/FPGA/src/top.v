/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved 
 * SiLab , Physics Institute of Bonn University , All Right 
 * ------------------------------------------------------------
 *
 * SVN revision information:
 *  $Rev::                       $:
 *  $Author::                    $:
 *  $Date::                      $:
 */
 
`timescale 1ps / 1ps
`default_nettype none

module top (
    
    input wire FCLK_IN, // 48MHz
    
    //full speed 
    inout wire [7:0] BUS_DATA,
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
    output wire [4:0] LED,
    
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
    input wire MONHIT,

    // FE CLK (SCC and BIC)
    output wire CMD_CLK,

    // FE DI (SCC and BIC)
    output wire CMD_DATA,

    // FE DOBOUT (SCC and BIC)
    // DOBOUT[0]: Ch1
    // DOBOUT[1]: Ch2
    // DOBOUT[2]: Ch3
    // DOBOUT[3]: Ch4 on BIC, DO on SCC
    input wire [3:0] DOBOUT,

    // Voltage Regulator Enable (SCC and BIC)
    // EN[0]: EN_VA1 on SCC, EN_VDD1 on BIC
    // EN[1]: EN_VA2 on SCC, EN_VDD2 on BIC
    // EN[2]: EN_VD2 on SCC, EN_VDD3 on BIC
    // EN[3]: EN_VD1 on SCC, EN_VDD4 on BIC
    output wire [3:0] EN,

    // Over Current Protection (BIC only)
    input wire [3:0] OC,

    // Select (SEL) LED (BIC only)
    // SEL[0]: Ch1
    // SEL[1]: Ch2
    // SEL[2]: Ch3
    // SEL[3]: Ch4 on BIC, DO on SCC
    output wire [3:0] SEL,

    //input wire FPGA_BUTTON // switch S2 on MultiIO board, active low

    // I2C
    inout SDA,
    inout SCL
);

wire BUS_RST;
wire BUS_CLK;
wire CLK_40;
wire RX_CLK;
wire RX_CLK2X;
wire DATA_CLK;
wire CLK_LOCKED;

//assign EN = 4'b1111;

//assign SEL = 4'b1111;

assign MULTI_IO = 11'b000_0000_0000;
assign DEBUG_D = 16'ha5a5;


wire LEMO_TRIGGER, LEMO_RESET, TDC_IN, TDC_OUT;
assign LEMO_TRIGGER = LEMO_RX[0];
assign LEMO_RESET = LEMO_RX[1];
assign TDC_IN = LEMO_RX[2];

// TLU
wire            RJ45_ENABLED;
wire            TLU_BUSY;               // busy signal to TLU to de-assert trigger
wire            TLU_CLOCK;

// CMD
wire            CMD_EXT_START_FLAG;     // to CMD FSM
wire            CMD_EXT_START_ENABLE;   // from CMD FSM
wire            CMD_READY;              // to TLU FSM
wire            CMD_START_FLAG;         // for triggering external devices
//reg             CMD_CAL;                // when CAL command is send

assign TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign TX[1] = TLU_BUSY | (CMD_START_FLAG/*CMD_CAL*/ & ~CMD_EXT_START_ENABLE); // TLU_BUSY signal; also connected to RJ45 output. Asserted when TLU FSM has accepted a trigger or when CMD FSM is busy. 
assign TX[2] = (RJ45_ENABLED == 1'b1) ? RJ45_TRIGGER : (LEMO_TRIGGER | MONHIT | TDC_OUT); // to trigger on MONHIT or TDC_OUT use loop back cable from TX2 to RX0


// ------- RESRT/CLOCK  ------- //
reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

clk_gen iclkgen(
    .U1_CLKIN_IN(FCLK_IN),
    .U1_RST_IN(1'b0),
    .U1_CLKIN_IBUFG_OUT(),
    .U1_CLK0_OUT(BUS_CLK), // DCM1: 48MHz USB/SRAM clock
    .U1_STATUS_OUT(),
    .U2_CLKFX_OUT(CLK_40), // DCM2: 40MHz command clock
    .U2_CLKDV_OUT(DATA_CLK), // DCM2: 16MHz SERDES clock
    .U2_CLK0_OUT(RX_CLK), // DCM2: 160MHz data clock
    .U2_CLK90_OUT(),
    .U2_CLK2X_OUT(RX_CLK2X), // DCM2: 320MHz data recovery clock
    .U2_LOCKED_OUT(CLK_LOCKED),
    .U2_STATUS_OUT()
);

// 1Hz CLK
wire CE_1HZ; // use for sequential logic
wire CLK_1HZ; // don't connect to clock input, only combinatorial logic
clock_divider #(
    .DIVISOR(40000000)
) i_clock_divisor_40MHz_to_1Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE(CE_1HZ),
    .CLOCK(CLK_1HZ)
);

wire CLK_2HZ;
clock_divider #(
    .DIVISOR(13000000)
) i_clock_divisor_40MHz_to_2Hz (
    .CLK(CLK_40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_2HZ)
);


// -------  MODULE ADREESSES  ------- //
localparam CMD_BASEADDR = 16'h0000;
localparam CMD_HIGHADDR = 16'h8000-1;

localparam FIFO_BASEADDR = 16'h8100;
localparam FIFO_HIGHADDR = 16'h8200-1;

localparam TLU_BASEADDR = 16'h8200;
localparam TLU_HIGHADDR = 16'h8300-1;

localparam RX4_BASEADDR = 16'h8300;
localparam RX4_HIGHADDR = 16'h8400-1;

localparam RX3_BASEADDR = 16'h8400;
localparam RX3_HIGHADDR = 16'h8500-1;

localparam RX2_BASEADDR = 16'h8500;
localparam RX2_HIGHADDR = 16'h8600-1;

localparam RX1_BASEADDR = 16'h8600;
localparam RX1_HIGHADDR = 16'h8700-1;

localparam TDC_BASEADDR = 16'h8700;
localparam TDC_HIGHADDR = 16'h8800-1;

localparam GPIO_RX_BASEADDR = 16'h8800;
localparam GPIO_RX_HIGHADDR = 16'h8900-1;

localparam GPIO_POWER_BASEADDR = 16'h8900;
localparam GPIO_POWER_HIGHADDR = 16'h8A00-1;

// -------  BUS SYGNALING  ------- //
wire [15:0] BUS_ADD;
assign BUS_ADD = ADD - 16'h4000;
wire BUS_RD, BUS_WR;
assign BUS_RD = ~RD_B;
assign BUS_WR = ~WR_B;


// -------  USER MODULES  ------- //

wire FIFO_NOT_EMPTY; // raised, when SRAM FIFO is not empty
wire FIFO_FULL, FIFO_NEAR_FULL; // raised, when SRAM FIFO is full / near full
wire FIFO_READ_ERROR; // raised, when attempting to read from SRAM FIFO when it is empty

cmd_seq 
#( 
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR)
)  icmd
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
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

parameter DSIZE = 10;
//parameter CLKIN_PERIOD = 6.250;

wire [3:0] RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL;
wire [3:0] FE_FIFO_READ;
wire [3:0] FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA [3:0];

genvar i;
generate
  for (i = 0; i < 4; i = i + 1) begin: rx_gen
    fei4_rx 
    #(
        .BASEADDR(RX1_BASEADDR-16'h0100*i),
        .HIGHADDR(RX1_HIGHADDR-16'h0100*i),
        .DSIZE(DSIZE),
        .DATA_IDENTIFIER(i+1)
    ) ifei4_rx
    (
        .RX_CLK(RX_CLK),
        .RX_CLK2X(RX_CLK2X),
        .DATA_CLK(DATA_CLK),
        
        .RX_DATA(DOBOUT[i]),
        
        .RX_READY(RX_READY[i]),
        .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR[i]),
        .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR[i]),
         
        .FIFO_READ(FE_FIFO_READ[i]),
        .FIFO_EMPTY(FE_FIFO_EMPTY[i]),
        .FIFO_DATA(FE_FIFO_DATA[i]),
        
        .RX_FIFO_FULL(RX_FIFO_FULL[i]),
         
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
    ); 
  end
endgenerate

wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
wire [31:0] TIMESTAMP;

tdc_s3
#(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100) // one-hot
) i_tdc
(
    .CLK320(RX_CLK2X),
    .CLK160(RX_CLK),
    .DV_CLK(CLK_40),
    .TDC_IN(TDC_IN),
    .TDC_OUT(TDC_OUT),

    .FIFO_READ(TDC_FIFO_READ),
    .FIFO_EMPTY(TDC_FIFO_EMPTY),
    .FIFO_DATA(TDC_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(CMD_START_FLAG), // arm TDC by sending commands
    .EXT_EN(1'b0),
    
    .TIMESTAMP(TIMESTAMP[15:0])
);

wire [3:0] NOT_CONNECTED_RX;
gpio 
#( 
    .BASEADDR(GPIO_RX_BASEADDR), 
    .HIGHADDR(GPIO_RX_HIGHADDR),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_RX, SEL[3], SEL[2], SEL[1], SEL[0]})
);

wire [3:0] NOT_CONNECTED_POWER;
gpio 
#( 
    .BASEADDR(GPIO_POWER_BASEADDR), 
    .HIGHADDR(GPIO_POWER_HIGHADDR),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio_power (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_POWER, EN[3], EN[2], EN[1], EN[0]}) //OC[3], OC[2], OC[1], OC[0]
);

wire TLU_FIFO_READ;
wire TLU_FIFO_EMPTY;
wire [31:0] TLU_FIFO_DATA;
wire TLU_FIFO_PEEMPT_REQ;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8)
) i_tlu_controller (

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CMD_CLK(CLK_40),
    
    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),
    
    .FIFO_PREEMPT_REQ(TLU_FIFO_PEEMPT_REQ),
    
    .RJ45_TRIGGER(RJ45_TRIGGER),
    .LEMO_TRIGGER(LEMO_TRIGGER),
    .RJ45_RESET(RJ45_RESET),
    .LEMO_RESET(LEMO_RESET),
    .RJ45_ENABLED(RJ45_ENABLED),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .EXT_VETO(FIFO_FULL),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    
    .TIMESTAMP(TIMESTAMP)
);

wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [5:0] READ_GRANT;

rrp_arbiter 
#( 
    .WIDTH(6)
) i_rrp_arbiter
(
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY, ~TLU_FIFO_EMPTY}),
    .HOLD_REQ({5'b0, TLU_FIFO_PEEMPT_REQ}),
    .DATA_IN({FE_FIFO_DATA[3],FE_FIFO_DATA[2],FE_FIFO_DATA[1], FE_FIFO_DATA[0], TDC_FIFO_DATA, TLU_FIFO_DATA }),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TLU_FIFO_READ = READ_GRANT[0];
assign FE_FIFO_READ = READ_GRANT[5:2];
assign TDC_FIFO_READ = READ_GRANT[1];


wire USB_READ;
assign USB_READ = FREAD & FSTROBE;

sram_fifo 
#(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR)
) i_out_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR), 

    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),

    .USB_READ(USB_READ),
    .USB_DATA(FDATA),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),

    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);
    
// ------- LEDs  ------- //
parameter VERSION = 4; // all on: 31
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
assign LED[0] = SHOW_VERSION? VERSION[0] : RX_READY[0] & ((RX_8B10B_DECODER_ERR[0]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[0] | RX_FIFO_FULL[0]);
assign LED[1] = SHOW_VERSION? VERSION[1] : RX_READY[1] & ((RX_8B10B_DECODER_ERR[1]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[1] | RX_FIFO_FULL[1]);
assign LED[2] = SHOW_VERSION? VERSION[2] : RX_READY[2] & ((RX_8B10B_DECODER_ERR[2]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[2] | RX_FIFO_FULL[2]);
assign LED[3] = SHOW_VERSION? VERSION[3] : RX_READY[3] & ((RX_8B10B_DECODER_ERR[3]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[3] | RX_FIFO_FULL[3]);
assign LED[4] = SHOW_VERSION? VERSION[4] : (((RJ45_ENABLED? CLK_2HZ : CLK_1HZ) | FIFO_FULL) & CLK_LOCKED);


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
