`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date:    14:37:22 03/22/2013 
// Design Name: 
// Module Name:    clk_gen 
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
module clk_gen(
    input CLKIN,
    output CLKINBUF,
    output CLKINBUF270,
    output CLKOUT160,
    output CLKOUT40,
    output CLKOUT5,
    output LOCKED
    );

	wire GND_BIT;
   assign GND_BIT = 0;
	
	wire CLKFX_BUF, CLKOUTFX, CLKDV, CLKDV_BUF;
	wire CLK0_BUF;
	
	assign CLKOUT160 = CLKOUTFX;
    
   wire CLK270_BUF;
   BUFG CLKFX_BUFG_INST (.I(CLKFX_BUF), .O(CLKOUTFX)); //most likley this in not need (free some resources)
   BUFG CLKFB_BUFG_INST (.I(CLK0_BUF), .O(CLKINBUF));
   BUFG CLK90_BUFG_INST (.I(CLK270_BUF), .O(CLKINBUF270));
   BUFG CLKDV_BUFG_INST (.I(CLKDV), .O(CLKDV_BUF));
   assign CLKOUT5 = CLKDV_BUF;

   DCM #(
		 .CLKDV_DIVIDE(10.0), // Divide by: 1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,6.5
		 // 7.0,7.5,8.0,9.0,10.0,11.0,12.0,13.0,14.0,15.0 or 16.0
		 .CLKFX_DIVIDE(6), // Can be any Integer from 1 to 32
		 .CLKFX_MULTIPLY(20), // Can be any Integer from 2 to 32
		 .CLKIN_DIVIDE_BY_2("FALSE"), // TRUE/FALSE to enable CLKIN divide by two feature
		 .CLKIN_PERIOD(20.833), // Specify period of input clock
		 .CLKOUT_PHASE_SHIFT("NONE"), // Specify phase shift of NONE, FIXED or VARIABLE
		 .CLK_FEEDBACK("1X"), // Specify clock feedback of NONE, 1X or 2X
		 .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), // SOURCE_SYNCHRONOUS, SYSTEM_SYNCHRONOUS or
		 // an Integer from 0 to 15
		 .DFS_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for frequency synthesis
		 .DLL_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for DLL
		 .DUTY_CYCLE_CORRECTION("TRUE"), // Duty cycle correction, TRUE or FALSE
		 .FACTORY_JF(16'hC080), // FACTORY JF values
		 .PHASE_SHIFT(0), // Amount of fixed phase shift from -255 to 255
		 .STARTUP_WAIT("TRUE") // Delay configuration DONE until DCM_SP LOCK, TRUE/FALSE
         ) DCM_BUS (
         .CLKFB(CLKINBUF), 
         .CLKIN(CLKIN), 
         .DSSEN(GND_BIT), 
         .PSCLK(GND_BIT), 
         .PSEN(GND_BIT), 
         .PSINCDEC(GND_BIT), 
         .RST(GND_BIT),
         .CLKDV(CLKDV),
         .CLKFX(CLKFX_BUF), 
         .CLKFX180(), 
         .CLK0(CLK0_BUF), 
         .CLK2X(), 
         .CLK2X180(), 
         .CLK90(), 
         .CLK180(), 
         .CLK270(CLK270_BUF), 
         .LOCKED(LOCKED), 
         .PSDONE(), 
         .STATUS());
  
   
   wire  CLKFX_40;
   BUFG CLKFX_2_BUFG_INST (.I(CLKFX_40), .O(CLKOUT40));
   
   DCM #(
		 .CLKDV_DIVIDE(16.0), // Divide by: 1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,6.5
		 // 7.0,7.5,8.0,9.0,10.0,11.0,12.0,13.0,14.0,15.0 or 16.0
		 .CLKFX_DIVIDE(4), // Can be any Integer from 1 to 32
		 .CLKFX_MULTIPLY(2), // Can be any Integer from 2 to 32
		 .CLKIN_DIVIDE_BY_2("TRUE"), // TRUE/FALSE to enable CLKIN divide by two feature
		 .CLKIN_PERIOD(6.25), // Specify period of input clock
		 .CLKOUT_PHASE_SHIFT("NONE"), // Specify phase shift of NONE, FIXED or VARIABLE
		 .CLK_FEEDBACK("NONE"), // Specify clock feedback of NONE, 1X or 2X
		 .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), // SOURCE_SYNCHRONOUS, SYSTEM_SYNCHRONOUS or
		 // an Integer from 0 to 15
		 .DFS_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for frequency synthesis
		 .DLL_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for DLL
		 .DUTY_CYCLE_CORRECTION("TRUE"), // Duty cycle correction, TRUE or FALSE
		 .FACTORY_JF(16'hC080), // FACTORY JF values
		 .PHASE_SHIFT(0), // Amount of fixed phase shift from -255 to 255
		 .STARTUP_WAIT("TRUE") // Delay configuration DONE until DCM_SP LOCK, TRUE/FALSE
	 ) DCM_CMD (
		 .DSSEN(GND_BIT), 
		 .CLK0(), // 0 degree DCM_SP CLK output
		 .CLK180(), // 180 degree DCM_SP CLK output
		 .CLK270(), // 270 degree DCM_SP CLK output
		 .CLK2X(), // 2X DCM_SP CLK output
		 .CLK2X180(), // 2X, 180 degree DCM_SP CLK out
		 .CLK90(), // 90 degree DCM_SP CLK output
		 .CLKDV(), // Divided DCM_SP CLK out (CLKDV_DIVIDE)
		 .CLKFX(CLKFX_40), // DCM_SP CLK synthesis out (M/D)
		 .CLKFX180(), // 180 degree CLK synthesis out
		 .LOCKED(), // DCM_SP LOCK status output
		 .PSDONE(), // Dynamic phase adjust done output
		 .STATUS(), // 8-bit DCM_SP status bits output
		 .CLKFB(), // DCM_SP clock feedback
		 .CLKIN(CLKOUT160), // Clock input (from IBUFG, BUFG or DCM_SP)
		 .PSCLK(GND_BIT), // Dynamic phase adjust clock input
		 .PSEN(GND_BIT), // Dynamic phase adjust enable input
		 .PSINCDEC(GND_BIT), // Dynamic phase adjust increment/decrement
		 .RST(GND_BIT)// // DCM_SP asynchronous reset input
	 );

     
     
endmodule
