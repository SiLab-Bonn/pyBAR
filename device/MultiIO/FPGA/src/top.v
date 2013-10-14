/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University
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
    
    input wire [3:0] DOBOUT, // BIC only, 0 - Ch1, 1 - Ch2, 2 - Ch3, 3 - DO on SCC, Ch4 on BIC
    
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


// ------- RESRT/CLOCK  ------- //
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

localparam GPIO_BASEADDR = 16'h9000;                    
localparam GPIO_HIGHADDR = GPIO_BASEADDR + 15;       


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
        .RX_CLK90(RX_CLK90),
        .DATA_CLK(DATA_CLK),
        .RX_CLK_LOCKED(CLK_LOCKED),
        
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

wire TLU_FIFO_READ;
wire TLU_FIFO_EMPTY;
wire [31:0] TLU_FIFO_DATA;
wire TLU_FIFO_PEEMPT_REQ;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(12)
) tlu_controller_module (

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
    
    .EXT_VETO(EXT_VETO),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),

    .FIFO_NEAR_FULL(FIFO_NEAR_FULL)
);


wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [7:0] READ_GRANT;
rrp_arbiter 
#( 
    .WIDTH(8), 
    .PRIORITY(8'b1000_0000)
) i_rrp_arbiter
(
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TLU_FIFO_EMPTY, ~FE_FIFO_EMPTY, 3'b0}),
    .HOLD_REQ({TLU_FIFO_PEEMPT_REQ, 7'b0}),
    .DATA_IN({TLU_FIFO_DATA,FE_FIFO_DATA[3],FE_FIFO_DATA[2],FE_FIFO_DATA[1], FE_FIFO_DATA[0], {3{32'b0}} }),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);
assign TLU_FIFO_READ = READ_GRANT[7];
assign FE_FIFO_READ = READ_GRANT[6:3];

wire USB_READ;
assign USB_READ = FREAD & FSTROBE;

sram_fifo 
#(
    .BASEADDR(FIFO_BASEADDR), 
    .HIGHADDR(FIFO_HIGHADDR)
) i_out_fifo (
    .BUS_CLK270(BUS_CLK270),
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
parameter VERSION = 3; // all on: 31
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
assign LED1 = SHOW_VERSION? VERSION[0] : (((RJ45_ENABLED? CLK_2HZ : CLK_1HZ) | FIFO_FULL) & CLK_LOCKED);
assign LED2 = SHOW_VERSION? VERSION[1] : RX_READY[0] & ((RX_8B10B_DECODER_ERR[0]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[0] | RX_FIFO_FULL[0]);
assign LED3 = SHOW_VERSION? VERSION[2] : RX_READY[1] & ((RX_8B10B_DECODER_ERR[1]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[1] | RX_FIFO_FULL[1]);
assign LED4 = SHOW_VERSION? VERSION[3] : RX_READY[2] & ((RX_8B10B_DECODER_ERR[2]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[2] | RX_FIFO_FULL[2]);
assign LED5 = SHOW_VERSION? VERSION[4] : RX_READY[3] & ((RX_8B10B_DECODER_ERR[3]? CLK_2HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[3] | RX_FIFO_FULL[3]);



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
