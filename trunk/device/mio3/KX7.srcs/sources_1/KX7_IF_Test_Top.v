`timescale 1ps/100fs
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
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
	 output wire fx3_pclk_100MHz,
//(* IOB = "FORCE" *)  input wire fx3_rd,  // force IOB register
//(* IOB = "FORCE" *)  input wire fx3_counten,  // force IOB register
(* IOB = "FORCE" *)  input wire fx3_wr,  // force IOB register
(* IOB = "FORCE" *)	 input wire fx3_cs, // async. signal
(* IOB = "FORCE" *)	 input wire fx3_oe, // async. signal
//(* IOB = "FORCE" *)	 input wire fx3_aden,// force IOB register
	 input wire fx3_rst,// async. signal
(* IOB = "FORCE" *)  output wire fx3_ack,// force IOB register
(* IOB = "FORCE" *)	 output wire fx3_rdy,// force IOB register
   output wire reset_fx3,
   inout wire [31:0] fx3_bus, // 32 bit databus

// DDR3 interface (256Mb x 8)
   /*inout  wire  [7:0]  ddr3_dq,
	 output wire  [14:0] ddr3_addr,
	 inout  wire  [0:0]ddr3_dqs_p,
	 inout  wire  [0:0]ddr3_dqs_n,
	 output wire  [2:0] ddr3_ba,
	 output wire  [0:0]ddr3_ck_p,
	 output wire  [0:0]ddr3_ck_n,
	 output wire  ddr3_ras_n,
	 output wire  ddr3_cas_n,
	 output wire  ddr3_we_n,
	 output wire  ddr3_reset_n,
	 output wire  [0:0]ddr3_cke,
	 output wire  [0:0]ddr3_odt,
	 output wire  [0:0]ddr3_cs_n,
	 output wire  [0:0]ddr3_dm,*/

// 200 MHz oscillator
	 input  wire  sys_clk_p, 
	 input  wire  sys_clk_n,
	 
// 100 Mhz oscillator
   input  wire  Clk100, 

//   output wire  INIT_COMPLETE, // Comment before synthesis!

// GPIO	 
   output wire [8:1] led,
   
//  output wire DDR3_VSEL,
   
// DMA_RDY
//(* IOB = "FORCE" *) input wire fx3_dma_rdy,
/*(* IOB = "FORCE" *)*/ output wire fx3_rd_finish, // still in IOB
   
   input wire Reset_button2,// async. signal
   
   input wire FLAG1, // DMA Flag
(* IOB = "FORCE" *) input wire FLAG2,

    output wire EN_VD1,
    output wire EN_VD2,
    output wire EN_VA1,
    output wire EN_VA2
    
);


// FX3 interface
 wire [31:0] DataOut; // data from FPGA to FX3
 wire [31:0] DataIn;  // data from FX3 to FPGA
 wire [31:0] BramOut;
 wire [31:0] Reg1;
 wire [31:0] Reg2;
 wire CLK_100MHz;
 wire WR;
 wire RD;
 wire RDYB;
 wire ACKB;
 wire [31:0]Addr;
 wire RST;
 
 wire Clk200;

 
 assign led[5:1] = 0;
 //assign led[7:1] = Reg1[6:0];
 //assign led[8] = fx3_dma_rdy;
 assign led[8] = 0;
 assign led[7] = 0;
 assign led[6] = FLAG1_reg;
// assign led[5] = DMA_RDY;
// assign led[4] = fx3_rd_finish;
// assign led[5] = FLAG2_reg;
 
 assign reset_fx3 = 1; // not to reset fx3 while loading fpga
 
 assign DDR3_VSEL = 1'bz;
 assign ddr3_cs_n = 0;
 assign ddr3_dm = 0;
 
 assign EN_VD1 = 1;
 assign EN_VD2 = 1;
 assign EN_VA1 = 1;
 assign EN_VA2 = 1;

FX3_IF  FX3_IF_inst (
    .fx3_bus(fx3_bus),
//    .fx3_rd(fx3_rd),
//    .fx3_counten(fx3_counten),
    .fx3_wr(fx3_wr),
    .fx3_oe(fx3_oe),
    .fx3_cs(fx3_cs),
//    .fx3_aden(fx3_aden),
    .fx3_clk(fx3_pclk_100MHz),
    .fx3_rdy(fx3_rdy),
    .fx3_ack(fx3_ack),
    .fx3_rd_finish(fx3_rd_finish),
//    .fx3_dma_rdy(fx3_dma_rdy),
    .fx3_rst(!fx3_rst), // Button is active low
//    .fx3_rst(fx3_rst), // Comment before synthesis and uncomment previous line

    .DataOut(DataOut), // data from FPGA core
    .DataIn(DataIn),   // data to FPGA core
    .WR(WR),
    .RD(RD),
    .FLAG1(FLAG1),
    .FLAG2(FLAG2),
    .FLAG1_reg(FLAG1_reg),
    .FLAG2_reg(FLAG2_reg),
    .Addr(Addr),
    .RDY_N(RDYB),
    .RD_VALID_N(ACKB),
//		.CLK_100MHz(CLK_100MHz),
        .CLK_100MHz(Clk100),  // Now clock for FX3 is generated with external oscillator, not DDR
		.RST(RST),
//	.DMA_RDY(DMA_RDY),
	.CS(CS_FX3)
    );
    
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