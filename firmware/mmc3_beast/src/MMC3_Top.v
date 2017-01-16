`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:        SILAB , Physics Institute of Bonn University
// Engineer:       Viacheslav Filimonov
// 
// Create Date:    10:40:28 12/16/2013 
// Design Name: 
// Module Name:    KX7_IF_Test_Top 
// Project Name: 
// Target Devices: 
// Tool versions: 
// Description: 
//
// Dependencies: 
//
// Revision: 
// Revision 0.01 - File Created
// Additional Comments: 
//
//////////////////////////////////////////////////////////////////////////////////

module KX7_IF_Test_Top(
// FX 3 interface
	input wire fx3_pclk_100MHz,
(* IOB = "FORCE" *)  input wire fx3_wr,  // force IOB register
(* IOB = "FORCE" *)	 input wire fx3_cs, // async. signal
(* IOB = "FORCE" *)	 input wire fx3_oe, // async. signal
	input wire fx3_rst, // async. signal from FX3, active high
(* IOB = "FORCE" *)  output wire fx3_ack,// force IOB register
(* IOB = "FORCE" *)	 output wire fx3_rdy,// force IOB register
//    output wire reset_fx3,
    inout wire [31:0] fx3_bus, // 32 bit databus

// 200 MHz oscillator
    input  wire  sys_clk_p, 
	input  wire  sys_clk_n,
	 
// 100 Mhz oscillator
    input  wire  Clk100, 

// GPIO	 
    output wire [4:1] led_module,
    output wire [4:1] led_baseboard,
   
(* IOB = "FORCE" *) output wire fx3_rd_finish,
   
    input wire Reset_button,// async. signal
   
    input wire FLAG1, // was DMA Flag; currently connected to TEST signal from FX3
(* IOB = "FORCE" *) input wire FLAG2, // DMA watermark flag for thread 2 of FX3

// Power supply regulators EN signals
    output wire [3:0] EN,
    
// Command sequencer signals
(* IOB = "FORCE" *) output wire [6:0] CMD_CLK_OUT_P,
(* IOB = "FORCE" *) output wire [6:0] CMD_CLK_OUT_N,

(* IOB = "FORCE" *) output wire [6:0] CMD_DATA_P,
(* IOB = "FORCE" *) output wire [6:0] CMD_DATA_N,
    
// FE-I4_rx signals
(* IOB = "FORCE" *) input wire [6:0] DOBOUT_P,
(* IOB = "FORCE" *) input wire [6:0] DOBOUT_N,

// Trigger
(* IOB = "FORCE" *) input wire [1:0] LEMO_RX,
    output wire [1:0] TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
(* IOB = "FORCE" *) input wire RJ45_RESET,
(* IOB = "FORCE" *) input wire RJ45_TRIGGER,

// TDC
(* IOB = "FORCE" *) input wire TDC_IN_P,
(* IOB = "FORCE" *) input wire TDC_IN_N
    
);

//assign reset_fx3 = 1; // not to reset fx3 while loading fpga

wire [31:0] BUS_ADD;
wire [31:0] BUS_DATA;

wire BUS_RD, BUS_WR, BUS_RST, BUS_CLK;
//assign BUS_RST = (BUS_RST | (!LOCKED));

wire BUS_BYTE_ACCESS;
assign BUS_BYTE_ACCESS = (BUS_ADD < 32'h8000_0000) ? 1'b1 : 1'b0;

wire RST;
assign RST = ((fx3_rst)|(!LOCKED)|(!Reset_button)); // Button is acticve low

FX3_IF  FX3_IF_inst (
    .fx3_bus(fx3_bus),
    .fx3_wr(fx3_wr),
    .fx3_oe(fx3_oe),
    .fx3_cs(fx3_cs),
    .fx3_clk(fx3_pclk_100MHz),
    .fx3_rdy(fx3_rdy),
    .fx3_ack(fx3_ack),
    .fx3_rd_finish(fx3_rd_finish),
    .fx3_rst(RST), // PLL is reset first

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .BUS_BYTE_ACCESS(BUS_BYTE_ACCESS),
    
    .FLAG1(FLAG1),
    .FLAG2(FLAG2)
    );

wire clk40mhz_pll, clk320mhz_pll, clk160mhz_pll, clk16mhz_pll, clk40mhz_phase_pll;
wire pll_feedback, LOCKED;

PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(64),       // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(10.000),      // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).
    
    .CLKOUT0_DIVIDE(32),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT0_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT0_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .CLKOUT1_DIVIDE(4),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT1_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT1_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .CLKOUT2_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT2_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT2_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .CLKOUT3_DIVIDE(80),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT3_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT3_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .CLKOUT4_DIVIDE(32),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT4_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT4_PHASE(45.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .DIVCLK_DIVIDE(5),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE")     // Delay DONE until PLL Locks, ("TRUE"/"FALSE")
 )
 PLLE2_BASE_inst (
     // Generated 40 MHz clock 
     .CLKOUT0(clk40mhz_pll),
     .CLKOUT1(clk320mhz_pll),
     .CLKOUT2(clk160mhz_pll),
     .CLKOUT3(clk16mhz_pll),
     .CLKOUT4(clk40mhz_phase_pll),
     .CLKOUT5(),
     
     .CLKFBOUT(pll_feedback),
     
     .LOCKED(LOCKED),     // 1-bit output: LOCK
     
     // Input 100 MHz clock
     .CLKIN1(BUS_CLK),
    
     // Control Ports
     .PWRDWN(0),
     .RST(fx3_rst), // Reset from FX3
    
     // Feedback
     .CLKFBIN(pll_feedback)
 );
 
 wire clk40mhz, clk320mhz, clk160mhz, clk16mhz, clk40mhz_phase;
 
 BUFG BUFG_inst_40 (
 .O(clk40mhz),     // Clock buffer output
 .I(clk40mhz_pll)      // Clock buffer input
 );
 
 BUFG BUFG_inst_320 (
 .O(clk320mhz),     // Clock buffer output
 .I(clk320mhz_pll)      // Clock buffer input
 );
 
 BUFG BUFG_inst_160 (
 .O(clk160mhz),     // Clock buffer output
 .I(clk160mhz_pll)      // Clock buffer input
 );
 
 BUFG BUFG_inst_16 (
 .O(clk16mhz),     // Clock buffer output
 .I(clk16mhz_pll)      // Clock buffer input
 );
 
 BUFG BUFG_inst_40_phase (
 .O(clk40mhz_phase),     // Clock buffer output
 .I(clk40mhz_phase_pll)      // Clock buffer input
 );
 
// -------  MODULE ADREESSES  ------- //
 localparam CMD_BASEADDR = 32'h0000;
 localparam CMD_HIGHADDR = 32'h8000-1;
 
 localparam FIFO_BASEADDR = 32'h8100;
 localparam FIFO_HIGHADDR = 32'h8200-1;
 
 localparam TLU_BASEADDR = 32'h8200;
 localparam TLU_HIGHADDR = 32'h8300-1;

 localparam RX8_BASEADDR = 32'h9300; // not used
 localparam RX8_HIGHADDR = 32'h9400-1; // not used
 
 localparam RX7_BASEADDR = 32'h9400;
 localparam RX7_HIGHADDR = 32'h9500-1;
 
 localparam RX6_BASEADDR = 32'h9500;
 localparam RX6_HIGHADDR = 32'h9600-1;
 
 localparam RX5_BASEADDR = 32'h9600;
 localparam RX5_HIGHADDR = 32'h9700-1;
 
 localparam RX4_BASEADDR = 32'h8300;
 localparam RX4_HIGHADDR = 32'h8400-1;
  
 localparam RX3_BASEADDR = 32'h8400;
 localparam RX3_HIGHADDR = 32'h8500-1;
  
 localparam RX2_BASEADDR = 32'h8500;
 localparam RX2_HIGHADDR = 32'h8600-1;
  
 localparam RX1_BASEADDR = 32'h8600;
 localparam RX1_HIGHADDR = 32'h8700-1;
 
 localparam TDC_BASEADDR = 32'h8700;
 localparam TDC_HIGHADDR = 32'h8800-1;
 
 localparam GPIO_POWER_BASEADDR = 32'h8900;
 localparam GPIO_POWER_HIGHADDR = 32'h8A00-1;
 
 localparam GPIO_DISABLE_BASEADDR = 32'h8A00;
 localparam GPIO_DISABLE_HIGHADDR = 32'h8B00-1;
 
 localparam FIFO_BASEADDR_DATA = 32'h8000_0000;
 localparam FIFO_HIGHADDR_DATA = 32'h9000_0000;
 
 localparam ABUSWIDTH = 32;
 localparam OUTPUTS = 7;

// gpio disable
wire [OUTPUTS-1:0] DIS_CH;

gpio #(
    .BASEADDR(GPIO_DISABLE_BASEADDR),
    .HIGHADDR(GPIO_DISABLE_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .IO_WIDTH(OUTPUTS),
    .IO_DIRECTION(8'hff)
) i_gpio_disable (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(DIS_CH[OUTPUTS-1:0])
);

// Command sequencer
wire CMD_EXT_START_FLAG, TLU_CMD_EXT_START_FLAG; // to CMD FSM
assign CMD_EXT_START_FLAG = TLU_CMD_EXT_START_FLAG;
//assign CMD_EXT_START_FLAG = 0;

wire CMD_EXT_START_ENABLE; // from CMD FSM
wire CMD_READY; // to TLU FSM
wire CMD_START_FLAG; // sending FE command triggered by external devices
wire [OUTPUTS-1:0] CMD_CLK_OUT;
wire [OUTPUTS-1:0] CMD_DATA;

cmd_seq 
#( 
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .OUTPUTS(OUTPUTS)
) icmd (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CMD_CLK_OUT(/*CMD_CLK_OUT*/),
    .CMD_CLK_IN(clk40mhz),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    .CMD_DATA(CMD_DATA),
    .CMD_READY(CMD_READY),
    .CMD_START_FLAG(CMD_START_FLAG),
    .DIS_CH(DIS_CH[OUTPUTS-1:0])
);
    	
// OBUFDS: Differential Output Buffer
//         Kintex-7
// Xilinx HDL Language Template, version 2014.4

genvar g;
generate
    for (g = 0; g < OUTPUTS; g = g + 1) begin: cmd_gen
    
        ODDR CMD_CLK_FORWARDING_INST (
            .Q(CMD_CLK_OUT[g]),
            .C(clk40mhz_phase),
            .CE(1'b1), 
            .D1(1'b1),
            .D2(1'b0),
            .R(1'b0),
            .S(1'b0)
        );
    
        OBUFDS #(
          .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
          .SLEW("SLOW")           // Specify the output slew rate
        ) OBUFDS_inst_cmd_clk_out (
          .O(CMD_CLK_OUT_P[g]),     // Diff_p output (connect directly to top-level port)
          .OB(CMD_CLK_OUT_N[g]),   // Diff_n output (connect directly to top-level port)
          .I(CMD_CLK_OUT[g])      // Buffer input 
        );

        OBUFDS #(
          .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
          .SLEW("SLOW")           // Specify the output slew rate
        ) OBUFDS_inst_cmd_data (
          .O(CMD_DATA_P[g]),     // Diff_p output (connect directly to top-level port)
          .OB(CMD_DATA_N[g]),   // Diff_n output (connect directly to top-level port)
          .I(CMD_DATA[g])      // Buffer input 
        );
    end
endgenerate

// FE-I4 RXs
parameter DSIZE = 10;
wire [6:0] FIFO_READ, FIFO_EMPTY;
wire [31:0] FIFO_DATA [6:0];
wire [6:0] DOBOUT;

genvar i;
generate
  for (i = 0; i < 4; i = i + 1) begin: rx_gen_i
  
    /*PULLDOWN PULLDOWN_DOBOUT_N_i (
        .O(DOBOUT_N[i])     // Pulldown output (connect directly to top-level port)
    );
     
    PULLUP PULLUP_DOBOUT_P_i (
        .O(DOBOUT_P[i])     // Pulldown output (connect directly to top-level port)
    );*/
    
    IBUFDS #(
        .DIFF_TERM("TRUE"),       // Differential Termination
        .IBUF_LOW_PWR("FALSE"),     // Low power="TRUE", Highest performance="FALSE" 
        .IOSTANDARD("LVDS_25")     // Specify the input I/O standard
     ) IBUFDS_inst_i (
        .O(DOBOUT[i]),  // Buffer output
        .I(DOBOUT_P[i]),  // Diff_p buffer input (connect directly to top-level port)
        .IB(DOBOUT_N[i]) // Diff_n buffer input (connect directly to top-level port)
     );
     
    fei4_rx 
    #(
        .BASEADDR(RX1_BASEADDR-32'h0100*i),
        .HIGHADDR(RX1_HIGHADDR-32'h0100*i),
        .DSIZE(DSIZE),
        .DATA_IDENTIFIER(i+1),
        .ABUSWIDTH(ABUSWIDTH)
    ) i_fei4_rx_i (
        .RX_CLK(clk160mhz),
        .RX_CLK2X(clk320mhz),
        .DATA_CLK(clk16mhz),
        
        .RX_DATA(DOBOUT[i]),
        
        .RX_READY(led_module[i+1]),
        .RX_8B10B_DECODER_ERR(),
        .RX_FIFO_OVERFLOW_ERR(),
         
        .FIFO_READ(FIFO_READ[i]),
        .FIFO_EMPTY(FIFO_EMPTY[i]),
        .FIFO_DATA(FIFO_DATA[i]),
        
        .RX_FIFO_FULL(),
         
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA[7:0]),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
    ); 
  end
endgenerate

genvar t;
generate
  for (t = 4; t < 7; t = t + 1) begin: rx_gen_t
  
    /*PULLDOWN PULLDOWN_DOBOUT_N_t (
        .O(DOBOUT_N[t])     // Pulldown output (connect directly to top-level port)
    );
       
    PULLUP PULLUP_DOBOUT_P_t (
        .O(DOBOUT_P[t])     // Pulldown output (connect directly to top-level port)
    );*/
  
    IBUFDS #(
        .DIFF_TERM("TRUE"),       // Differential Termination
        .IBUF_LOW_PWR("FALSE"),     // Low power="TRUE", Highest performance="FALSE" 
        .IOSTANDARD("LVDS_25")     // Specify the input I/O standard
     ) IBUFDS_inst_t (
        .O(DOBOUT[t]),  // Buffer output
        .I(DOBOUT_P[t]),  // Diff_p buffer input (connect directly to top-level port)
        .IB(DOBOUT_N[t]) // Diff_n buffer input (connect directly to top-level port)
     );
     
    fei4_rx 
    #(
        .BASEADDR(RX5_BASEADDR-32'h0100*(t-4)),
        .HIGHADDR(RX5_HIGHADDR-32'h0100*(t-4)),
        .DSIZE(DSIZE),
        .DATA_IDENTIFIER(t+1),
        .ABUSWIDTH(ABUSWIDTH)
    ) i_fei4_rx_t (
        .RX_CLK(clk160mhz),
        .RX_CLK2X(clk320mhz),
        .DATA_CLK(clk16mhz),
        
        .RX_DATA(DOBOUT[t]),
        
        .RX_READY(),
        .RX_8B10B_DECODER_ERR(),
        .RX_FIFO_OVERFLOW_ERR(),
         
        .FIFO_READ(FIFO_READ[t]),
        .FIFO_EMPTY(FIFO_EMPTY[t]),
        .FIFO_DATA(FIFO_DATA[t]),
        
        .RX_FIFO_FULL(),
         
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA[7:0]),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
    ); 
  end
endgenerate

// gpio power
wire [3:0] NOT_CONNECTED_POWER;
gpio #(
    .BASEADDR(GPIO_POWER_BASEADDR),
    .HIGHADDR(GPIO_POWER_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio_power (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_POWER, EN[3], EN[2], EN[1], EN[0]}) //OC[3], OC[2], OC[1], OC[0]
);

// declarations for BRAM
wire FIFO_NOT_EMPTY, FIFO_FULL, FIFO_NEAR_FULL, FIFO_READ_ERROR;

// TDC
wire TDC_IN;
wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
wire [31:0] TIMESTAMP;

wire LEMO_TRIGGER, LEMO_TRIGGER_OUT;
assign LEMO_TRIGGER = LEMO_RX[0];

IBUFDS #(
    .DIFF_TERM("TRUE"),       // Differential Termination
    .IBUF_LOW_PWR("FALSE"),     // Low power="TRUE", Highest performance="FALSE" 
    .IOSTANDARD("LVDS_25")     // Specify the input I/O standard
 ) IBUFDS_inst_tdc (
    .O(TDC_IN),  // Buffer output
    .I(TDC_IN_P),  // Diff_p buffer input (connect directly to top-level port)
    .IB(TDC_IN_N) // Diff_n buffer input (connect directly to top-level port)
 );

tdc_s3 #(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100) // one-hot
) i_tdc (
    .CLK320(clk320mhz),
    .CLK160(clk160mhz),
    .DV_CLK(clk40mhz),
    .TDC_IN(TDC_IN),
    .TDC_OUT(),
    .TRIG_IN(LEMO_TRIGGER),
    .TRIG_OUT(LEMO_TRIGGER_OUT),

    .FIFO_READ(TDC_FIFO_READ),
    .FIFO_EMPTY(TDC_FIFO_EMPTY),
    .FIFO_DATA(TDC_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(CMD_START_FLAG), // arm TDC by sending commands
    .EXT_EN(1'b0),
    
    .TIMESTAMP(TIMESTAMP[15:0])
);

// TLU
wire TLU_FIFO_READ;
wire TLU_FIFO_EMPTY;
wire [31:0] TLU_FIFO_DATA;
wire TLU_FIFO_PEEMPT_REQ;

wire TLU_BUSY; // busy signal to TLU to de-assert trigger
wire TLU_CLOCK;

wire LEMO_RESET;
assign LEMO_RESET = LEMO_RX[1];

//assign TX[0]= TDC_IN;
assign TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign TX[1] = TLU_BUSY | (~CMD_READY/*CMD_CAL*/ & ~CMD_EXT_START_ENABLE); // TLU_BUSY signal; also connected to RJ45 output. Asserted when TLU FSM has accepted a trigger or when CMD FSM is busy (when CMD_EXT_START_ENABLE is disabled).

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .DIVISOR(8)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .CMD_CLK(clk40mhz),

    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),

    .FIFO_PREEMPT_REQ(TLU_FIFO_PEEMPT_REQ),

    .RJ45_TRIGGER(RJ45_TRIGGER),
    .LEMO_TRIGGER(LEMO_TRIGGER_OUT),
    .RJ45_RESET(RJ45_RESET),
    .LEMO_RESET(LEMO_RESET),
    .RJ45_ENABLED(),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .EXT_VETO(FIFO_FULL),
    
    .CMD_READY(CMD_READY),
    .CMD_EXT_START_FLAG(TLU_CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(CMD_EXT_START_ENABLE),
    
    .TIMESTAMP(TIMESTAMP)
);

// Arbiter
wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [8:0] READ_GRANT;

rrp_arbiter
#( 
    .WIDTH(9)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~FIFO_EMPTY, ~TDC_FIFO_EMPTY, ~TLU_FIFO_EMPTY}),
    .HOLD_REQ({8'b0, TLU_FIFO_PEEMPT_REQ}),
    .DATA_IN({FIFO_DATA[6], FIFO_DATA[5], FIFO_DATA[4], FIFO_DATA[3], FIFO_DATA[2], FIFO_DATA[1], FIFO_DATA[0], TDC_FIFO_DATA, TLU_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TLU_FIFO_READ = READ_GRANT[0];
assign TDC_FIFO_READ = READ_GRANT[1];
assign FIFO_READ = READ_GRANT[8:2];

// BRAM
bram_fifo 
#(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR),
    .BASEADDR_DATA(FIFO_BASEADDR_DATA),
    .HIGHADDR_DATA(FIFO_HIGHADDR_DATA),
    .ABUSWIDTH(ABUSWIDTH)
) i_out_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),

    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);

assign led_baseboard[1] = FIFO_NOT_EMPTY;
assign led_baseboard[2] = FIFO_FULL;
assign led_baseboard[3] = FIFO_NEAR_FULL;
assign led_baseboard[4] = FIFO_READ_ERROR;

/*always @ (posedge BUS_CLK)
begin
if (BUS_RST)
    begin
       led[5] <= 0;
       led[6] <= 0;
       led[7] <= 0;
       led[8] <= 0;
    end
else
    begin
        if (FIFO_NOT_EMPTY)
            led[5] <= 1;
        else if (FIFO_FULL)
            led[6] <= 1;
        else if (FIFO_NEAR_FULL)
            led[7] <= 1;
        else if (FIFO_READ_ERROR)
            led[8] <= 1;
    end
end*/

/*
gpio 
#( 
    .BASEADDR(GPIO_BASEADDR), 
    .HIGHADDR(GPIO_HIGHADDR),
    .ABUSWIDTH(32),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(led[8:1])
);

*/

/*Register #(
    .REG_SIZE(32), 
    .ADDRESS(1))
Reg1_inst (
    .D(DataIn), 
    .WR(WR), 
    .RD(RD), 
    .Addr(Addr),
    .CLK(CLK_100MHz), 
	  .Q(Reg1),
    .RB(DataOut), 
		.RDYB(RDYB),
		.RD_VALID_N(ACKB),
    .RST(RST)
    );
    
Register #(
    .REG_SIZE(32), 
    .ADDRESS(2))
Reg2_inst (
    .D(DataIn), 
    .WR(WR), 
    .RD(RD), 
    .Addr(Addr),
    .CLK(CLK_100MHz), 
	  .Q(Reg2),
    .RB(DataOut), 
		.RDYB(RDYB),
		.RD_VALID_N(ACKB),
    .RST(RST)
    );		
    
BRAM_Test #(
    .ADDRESS( 32'h10_00_00_00),
    .MEM_SIZE(32'h00_00_40_00))
BRAM_Test_inst (
    .DataIn(DataIn), 
    .WR(WR), 
    .RD(RD), 
    .CLK(CLK_100MHz), 
    .DataOut(DataOut), 
    .Addr(Addr[31:0]),
		.RDYB(RDYB),
		.RD_VALID_N(ACKB),
//	.DMA_RDY(DMA_RDY),
	.RST(RST)
    );    

DDR3_256_8  #(
    .ADDRESS( 32'h20_00_00_00), 
    .MEM_SIZE(32'h10_00_00_00)) 
DDR3_256_8_inst (
    .DataIn(DataIn[31:0]), 
    .WR(WR), 
    .RD(RD), 
    .Addr(Addr[31:0]), 
    .DataOut(DataOut[31:0]), 
    .RDY_N(RDYB), 
    .RD_VALID_N(ACKB), 
    .CLK_OUT(CLK_100MHz), 
    .RST(RST), 
    .Reset_button2(Reset_button2),
    .INIT_COMPLETE(INIT_COMPLETE),
    .ddr3_dq(ddr3_dq), 
    .ddr3_addr(ddr3_addr), 
//    .ddr3_dm(ddr3_dm), 
    .ddr3_dqs_p(ddr3_dqs_p), 
    .ddr3_dqs_n(ddr3_dqs_n), 
    .ddr3_ba(ddr3_ba), 
    .ddr3_ck_p(ddr3_ck_p), 
    .ddr3_ck_n(ddr3_ck_n), 
    .ddr3_ras_n(ddr3_ras_n), 
    .ddr3_cas_n(ddr3_cas_n), 
    .ddr3_we_n(ddr3_we_n), 
    .ddr3_reset_n(ddr3_reset_n), 
    .ddr3_cke(ddr3_cke), 
    .ddr3_odt(ddr3_odt), 
//    .ddr3_cs_n(ddr3_cs_n), 
    .sys_clk_p(sys_clk_p), 
    .sys_clk_n(sys_clk_n),
    .Clk100(Clk100),
    .full_fifo(full_fifo),
//    .DMA_RDY(DMA_RDY),
    .CS_FX3(CS_FX3),
    .FLAG2_reg(FLAG2_reg)
    );	*/	

endmodule