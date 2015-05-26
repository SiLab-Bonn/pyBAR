
`timescale 1ns / 1ps

module clock_manager(CLKIN1_IN, 
                     RST_IN, 
                     CLKOUT0_OUT, 
                     CLKOUT1_OUT, 
                     CLKOUT2_OUT, 
                     CLKOUT3_OUT,
                     CLKOUT0_OUT2,
                     LOCKED_OUT);

    input CLKIN1_IN;
    input RST_IN;
   output CLKOUT0_OUT;
   output CLKOUT1_OUT;
   output CLKOUT2_OUT;
   output CLKOUT3_OUT;
   output LOCKED_OUT;
   output wire CLKOUT0_OUT2;
   
   wire CLKFBOUT_CLKFBIN;
   wire CLKIN1_IBUFG;
   wire CLKOUT0_BUF;
   wire CLKOUT1_BUF;
   wire CLKOUT2_BUF;
   wire CLKOUT3_BUF;
   wire GND_BIT;
   wire [4:0] GND_BUS_5;
   wire [15:0] GND_BUS_16;
   wire VCC_BIT;
   
   assign GND_BIT = 0;
   assign GND_BUS_5 = 5'b00000;
   assign GND_BUS_16 = 16'b0000000000000000;
   assign VCC_BIT = 1;
   
   IBUFG  CLKIN1_IBUFG_INST (.I(CLKIN1_IN), 
                            .O(CLKIN1_IBUFG));
   BUFG  CLKOUT0_BUFG_INST (.I(CLKOUT0_BUF), 
                           .O(CLKOUT0_OUT));
   BUFG  CLKOUT1_BUFG_INST (.I(CLKOUT1_BUF), 
                           .O(CLKOUT1_OUT));
   BUFG  CLKOUT2_BUFG_INST (.I(CLKOUT2_BUF), 
                           .O(CLKOUT2_OUT));
   BUFG  CLKOUT3_BUFG_INST (.I(CLKOUT3_BUF), 
                           .O(CLKOUT3_OUT));
   PLL_ADV #( .BANDWIDTH("OPTIMIZED"), 
         .CLKIN1_PERIOD(20.000), 
         .CLKIN2_PERIOD(10.000), 
         .CLKOUT0_DIVIDE(4), 
         .CLKOUT1_DIVIDE(2), 
         .CLKOUT2_DIVIDE(40), 
         .CLKOUT3_DIVIDE(16), 
         .CLKOUT0_PHASE(0.000), 
         .CLKOUT1_PHASE(0.000), 
         .CLKOUT2_PHASE(0.000), 
         .CLKOUT3_PHASE(0.000), 
         .CLKOUT0_DUTY_CYCLE(0.500), 
         .CLKOUT1_DUTY_CYCLE(0.500), 
         .CLKOUT2_DUTY_CYCLE(0.500), 
         .CLKOUT3_DUTY_CYCLE(0.500), 
         .COMPENSATION("SYSTEM_SYNCHRONOUS"), 
         .DIVCLK_DIVIDE(1), 
         .CLKFBOUT_MULT(13), //650
         .CLKFBOUT_PHASE(0.0), 
         .REF_JITTER(0.005000) ) 
         PLL_ADV_INST (.CLKFBIN(CLKFBOUT_CLKFBIN), 
                         .CLKINSEL(VCC_BIT), 
                         .CLKIN1(CLKIN1_IBUFG), 
                         .CLKIN2(GND_BIT), 
                         .DADDR(GND_BUS_5[4:0]), 
                         .DCLK(GND_BIT), 
                         .DEN(GND_BIT), 
                         .DI(GND_BUS_16[15:0]), 
                         .DWE(GND_BIT), 
                         .REL(GND_BIT), 
                         .RST(RST_IN), 
                         .CLKFBDCM(), 
                         .CLKFBOUT(CLKFBOUT_CLKFBIN), 
                         .CLKOUTDCM0(), 
                         .CLKOUTDCM1(), 
                         .CLKOUTDCM2(), 
                         .CLKOUTDCM3(), 
                         .CLKOUTDCM4(), 
                         .CLKOUTDCM5(), 
                         .CLKOUT0(CLKOUT0_BUF), 
                         .CLKOUT1(CLKOUT1_BUF), 
                         .CLKOUT2(CLKOUT2_BUF), 
                         .CLKOUT3(CLKOUT3_BUF), 
                         .CLKOUT4(), 
                         .CLKOUT5(), 
                         .DO(), 
                         .DRDY(), 
                         .LOCKED(LOCKED_OUT));
      
    wire CLKOUT0_BUF2, CLKFBOUT_CLKFBIN2;      
    BUFG  CLKOUT0_BUFG_INST2 (.I(CLKOUT0_BUF2), 
                           .O(CLKOUT0_OUT2));
                           
     PLL_ADV #( .BANDWIDTH("OPTIMIZED"), 
         .CLKIN1_PERIOD(20.000), 
         .CLKIN2_PERIOD(10.000), 
         .CLKOUT0_DIVIDE(4), 
         .CLKOUT0_PHASE(0.000), 
         .CLKOUT0_DUTY_CYCLE(0.500), 
         .COMPENSATION("SYSTEM_SYNCHRONOUS"), 
         .DIVCLK_DIVIDE(1), 
         .CLKFBOUT_MULT(10), //650
         .CLKFBOUT_PHASE(0.0), 
         .REF_JITTER(0.005000) ) 
          PLL_ADV_INST2 (
             .CLKFBIN(CLKFBOUT_CLKFBIN2), 
             .CLKINSEL(VCC_BIT), 
             .CLKIN1(CLKIN1_IBUFG), 
             .CLKIN2(GND_BIT), 
             .DADDR(GND_BUS_5[4:0]), 
             .DCLK(GND_BIT), 
             .DEN(GND_BIT), 
             .DI(GND_BUS_16[15:0]), 
             .DWE(GND_BIT), 
             .REL(GND_BIT), 
             .RST(RST_IN), 
             .CLKFBDCM(), 
             .CLKFBOUT(CLKFBOUT_CLKFBIN2), 
             .CLKOUTDCM0(), 
             .CLKOUTDCM1(), 
             .CLKOUTDCM2(), 
             .CLKOUTDCM3(), 
             .CLKOUTDCM4(), 
             .CLKOUTDCM5(), 
             .CLKOUT0(CLKOUT0_BUF2), 
             .CLKOUT1(), 
             .CLKOUT2(), 
             .CLKOUT3(), 
             .CLKOUT4(), 
             .CLKOUT5(), 
             .DO(), 
             .DRDY(), 
             .LOCKED());
                         
endmodule
