/**
 * This file is part of pyBAR.
 * 
 * pyBAR is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * pyBAR is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with pyBAR.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */

`timescale 1ps / 1ps
`default_nettype none

module top (
    input wire USER_RESET,
    input wire USER_CLOCK,

    input wire ETH_COL,
    input wire ETH_CRS,
    
    output wire ETH_MDC,
    inout wire ETH_MDIO,
    output wire ETH_RESET_n,
    
    input wire ETH_RX_CLK,
    input wire [3:0] ETH_RX_D,
    input wire ETH_RX_DV,
    input wire ETH_RX_ER,
   
    input wire ETH_TX_CLK, 
    output wire [3:0] ETH_TX_D,
    output wire ETH_TX_EN,
    
    output wire [3:0] GPIO_LED,
    input wire [3:0] GPIO_DIP,
    inout wire SDA, SCL,
    
    output wire CMD_CLK, CMD_DATA,
    input wire [3:0] DOBOUT
    
);

    wire CLKFBOUT, CLKOUT0, CLKOUT1, CLKOUT2, CLKOUT3, CLKOUT4, CLKOUT5, CLKFBIN, LOCKED;
    wire RST, BUS_CLK, BUS_RST, SPI_CLK;
    
   PLL_BASE #(
      .BANDWIDTH("OPTIMIZED"),             // "HIGH", "LOW" or "OPTIMIZED" 
      .CLKFBOUT_MULT(16),                   // Multiply value for all CLKOUT clock outputs (1-64)
      .CLKFBOUT_PHASE(0.0),                // Phase offset in degrees of the clock feedback output (0.0-360.0).
      .CLKIN_PERIOD(25.0),                  // Input clock period in ns to ps resolution (i.e. 33.333 is 30
                                           // MHz).
      // CLKOUT0_DIVIDE - CLKOUT5_DIVIDE: Divide amount for CLKOUT# clock output (1-128)
      .CLKOUT0_DIVIDE(1), //640 - 320MHz 
      .CLKOUT1_DIVIDE(32), //25
      .CLKOUT2_DIVIDE(64), //10HHz
      .CLKOUT3_DIVIDE(16), //40MHz
      .CLKOUT4_DIVIDE(4), // 160Mhz
      .CLKOUT5_DIVIDE(40), //16Mhz
      // CLKOUT0_DUTY_CYCLE - CLKOUT5_DUTY_CYCLE: Duty cycle for CLKOUT# clock output (0.01-0.99).
      .CLKOUT0_DUTY_CYCLE(0.5),
      .CLKOUT1_DUTY_CYCLE(0.5),
      .CLKOUT2_DUTY_CYCLE(0.5),
      .CLKOUT3_DUTY_CYCLE(0.5),
      .CLKOUT4_DUTY_CYCLE(0.5),
      .CLKOUT5_DUTY_CYCLE(0.5),
      // CLKOUT0_PHASE - CLKOUT5_PHASE: Output phase relationship for CLKOUT# clock output (-360.0-360.0).
      .CLKOUT0_PHASE(0.0),
      .CLKOUT1_PHASE(0.0),
      .CLKOUT2_PHASE(0.0),
      .CLKOUT3_PHASE(0.0),
      .CLKOUT4_PHASE(0.0),
      .CLKOUT5_PHASE(0.0),
      .CLK_FEEDBACK("CLKFBOUT"),           // Clock source to drive CLKFBIN ("CLKFBOUT" or "CLKOUT0")
      .COMPENSATION("SYSTEM_SYNCHRONOUS"), // "SYSTEM_SYNCHRONOUS", "SOURCE_SYNCHRONOUS", "EXTERNAL" 
      .DIVCLK_DIVIDE(1),                   // Division value for all output clocks (1-52)
      .REF_JITTER(0.1),                    // Reference Clock Jitter in UI (0.000-0.999).
      .RESET_ON_LOSS_OF_LOCK("FALSE")      // Must be set to FALSE
   )
   PLL_BASE_inst (
      .CLKFBOUT(CLKFBOUT), // 1-bit output: PLL_BASE feedback output
      // CLKOUT0 - CLKOUT5: 1-bit (each) output: Clock outputs
      .CLKOUT0(CLKOUT0),
      .CLKOUT1(CLKOUT1),
      .CLKOUT2(CLKOUT2),
      .CLKOUT3(CLKOUT3),
      .CLKOUT4(CLKOUT4),
      .CLKOUT5(CLKOUT5),
      .LOCKED(LOCKED),     // 1-bit output: PLL_BASE lock status output
      .CLKFBIN(CLKFBIN),   // 1-bit input: Feedback clock input
      .CLKIN(USER_CLOCK),       // 1-bit input: Clock input
      .RST(USER_RESET)            // 1-bit input: Reset input
   );
   
    wire RX_CLK, TX_CLK;
    assign RST = USER_RESET | !LOCKED;
    assign CLKFBIN = CLKFBOUT; //BUFG BUFG_FB (  .O(CLKFBIN),  .I(CLKFBOUT) );
    BUFG BUFG_BUS (  .O(BUS_CLK),  .I(CLKOUT3) );
    BUFG BUFG_ETH_RX_CLK (  .O(RX_CLK),  .I(ETH_RX_CLK) );
    //BUFG BUFG_SPI(  .O(SPI_CLK),  .I(CLKOUT2) );
    BUFG BUFG_ETH_TX_CLK (  .O(TX_CLK),  .I(ETH_TX_CLK) );
    
    wire RX_320_CLK, RX_160_CLK, RX_16_CLK;
    //BUFG BUFG_RX_320 (  .O(RX_320_CLK),  .I(CLKOUT0) );
    //assign RX_320_CLK = CLKOUT0;
    BUFG BUFG_RX_160 (  .O(RX_160_CLK),  .I(CLKOUT4) );
    BUFG BUFG_RX_16 (  .O(RX_16_CLK),  .I(CLKOUT5) );
    
    //wire CLKOUT0_BUF;
    //BUFG BUFG_RX_320 (  .O(CLKOUT0_BUF),  .I(CLKOUT0) );
    
    wire CLK_40;
    assign CLK_40 = BUS_CLK;
        
    wire IOCLK, DIVCLK, DIVCLK_BUF, RX_320_IOCE;
    /*
    BUFIO2 #(
      .DIVIDE(4),             // DIVCLK divider (1,3-8)
      .DIVIDE_BYPASS("TRUE"), // Bypass the divider circuitry (TRUE/FALSE)
      .I_INVERT("FALSE"),     // Invert clock (TRUE/FALSE)
      .USE_DOUBLER("FALSE")   // Use doubler circuitry (TRUE/FALSE)
    )
    BUFIO2_inst (
      .DIVCLK(DIVCLK_BUF),             // 1-bit output: Divided clock output
      .IOCLK(RX_320_CLK),               // 1-bit output: I/O output clock
      .SERDESSTROBE(RX_320_IOCE), // 1-bit output: Output SERDES strobe (connect to ISERDES2/OSERDES2)
      .I(CLKOUT3_BUF)                        // 1-bit input: Clock input (connect to IBUFG)
    );

    BUFG BUFG_DIV (  .O(RX_160_CLK),  .I(DIVCLK_BUF) );
    */
    
   BUFPLL #(
      .DIVIDE(4),           // DIVCLK divider (1-8)
      .ENABLE_SYNC("TRUE")  // Enable synchrnonization between PLL and GCLK (TRUE/FALSE)
   )
   BUFPLL_inst (
      .IOCLK(RX_320_CLK),               // 1-bit output: Output I/O clock
      .LOCK(),                 // 1-bit output: Synchronized LOCK output
      .SERDESSTROBE(RX_320_IOCE), // 1-bit output: Output SERDES strobe (connect to ISERDES2/OSERDES2)
      .GCLK(RX_160_CLK),                 // 1-bit input: BUFG clock input
      .LOCKED(LOCKED),             // 1-bit input: LOCKED input from PLL
      .PLLIN(CLKOUT0)                // 1-bit input: Clock input from PLL
   );
   
    wire EEPROM_CS, EEPROM_SK, EEPROM_DI;
    wire TCP_CLOSE_REQ;
    wire RBCP_ACT, RBCP_WE, RBCP_RE;
    wire [7:0] RBCP_WD, RBCP_RD;
    wire [31:0] RBCP_ADDR;
    wire TCP_RX_WR;
    wire [7:0] TCP_RX_DATA;
    wire RBCP_ACK;
    wire TCP_TX_FULL;
    wire TCP_TX_WR;
    wire [7:0] TCP_TX_DATA;
     
    wire   mdio_gem_i;
    wire   mdio_gem_o;
    wire   mdio_gem_t;

    wire [3:0] ETH_TX_D_NO;
    WRAP_SiTCP_GMII_XC6S_16K #(.TIM_PERIOD(50))sitcp(
      .CLK(BUS_CLK)                    ,    // in    : System Clock >129MHz
      .RST(RST)                    ,    // in    : System reset
    // Configuration parameters
      .FORCE_DEFAULTn(1'b0)        ,    // in    : Load default parameters
      .EXT_IP_ADDR(32'hc0a80a10)            ,    // in    : IP address[31:0] //192.168.10.16
      .EXT_TCP_PORT(16'd24)        ,    // in    : TCP port #[15:0]
      .EXT_RBCP_PORT(16'd4660)        ,    // in    : RBCP port #[15:0]
      .PHY_ADDR(5'd30)            ,    // in    : PHY-device MIF address[4:0]
    // EEPROM
      .EEPROM_CS()            ,    // out    : Chip select
      .EEPROM_SK()            ,    // out    : Serial data clock
      .EEPROM_DI()            ,    // out    : Serial write data
      .EEPROM_DO(1'b0)            ,    // in    : Serial read data
      // user data, intialial values are stored in the EEPROM, 0xFFFF_FC3C-3F
      .USR_REG_X3C()            ,    // out    : Stored at 0xFFFF_FF3C
      .USR_REG_X3D()            ,    // out    : Stored at 0xFFFF_FF3D
      .USR_REG_X3E()            ,    // out    : Stored at 0xFFFF_FF3E
      .USR_REG_X3F()            ,    // out    : Stored at 0xFFFF_FF3F
    // MII interface
      .GMII_RSTn(ETH_RESET_n)            ,    // out    : PHY reset
      .GMII_1000M(1'b0)            ,    // in    : GMII mode (0:MII, 1:GMII)
      // TX 
      .GMII_TX_CLK(TX_CLK)            ,    // in    : Tx clock
      .GMII_TX_EN(ETH_TX_EN)            ,    // out    : Tx enable
      .GMII_TXD({ETH_TX_D_NO,ETH_TX_D})            ,    // out    : Tx data[7:0]
      .GMII_TX_ER()            ,    // out    : TX error
      // RX
      .GMII_RX_CLK(RX_CLK)           ,    // in    : Rx clock
      .GMII_RX_DV(ETH_RX_DV)            ,    // in    : Rx data valid
      .GMII_RXD({4'b0, ETH_RX_D})            ,    // in    : Rx data[7:0]
      .GMII_RX_ER(ETH_RX_ER)            ,    // in    : Rx error
      .GMII_CRS(ETH_CRS)            ,    // in    : Carrier sense
      .GMII_COL(ETH_COL)            ,    // in    : Collision detected
      // Management IF
      .GMII_MDC(ETH_MDC)            ,    // out    : Clock for MDIO
      .GMII_MDIO_IN(mdio_gem_i)        ,    // in    : Data
      .GMII_MDIO_OUT(mdio_gem_o)        ,    // out    : Data
      .GMII_MDIO_OE(mdio_gem_t)        ,    // out    : MDIO output enable
    // User I/F
      .SiTCP_RST(BUS_RST)            ,    // out    : Reset for SiTCP and related circuits
      // TCP connection control
      .TCP_OPEN_REQ(1'b0)        ,    // in    : Reserved input, shoud be 0
      .TCP_OPEN_ACK()        ,    // out    : Acknowledge for open (=Socket busy)
      .TCP_ERROR()            ,    // out    : TCP error, its active period is equal to MSL
      .TCP_CLOSE_REQ(TCP_CLOSE_REQ)        ,    // out    : Connection close request
      .TCP_CLOSE_ACK(TCP_CLOSE_REQ)        ,    // in    : Acknowledge for closing
      // FIFO I/F
      .TCP_RX_WC(1'b1)            ,    // in    : Rx FIFO write count[15:0] (Unused bits should be set 1)
      .TCP_RX_WR(TCP_RX_WR)            ,    // out    : Write enable
      .TCP_RX_DATA(TCP_RX_DATA)            ,    // out    : Write data[7:0]
      .TCP_TX_FULL(TCP_TX_FULL)            ,    // out    : Almost full flag
      .TCP_TX_WR(TCP_TX_WR)            ,    // in    : Write enable
      .TCP_TX_DATA(TCP_TX_DATA)            ,    // in    : Write data[7:0]
      // RBCP
      .RBCP_ACT(RBCP_ACT)            ,    // out    : RBCP active
      .RBCP_ADDR(RBCP_ADDR)            ,    // out    : Address[31:0]
      .RBCP_WD(RBCP_WD)                ,    // out    : Data[7:0]
      .RBCP_WE(RBCP_WE)                ,    // out    : Write enable
      .RBCP_RE(RBCP_RE)                ,    // out    : Read enable
      .RBCP_ACK(RBCP_ACK)            ,    // in    : Access acknowledge
      .RBCP_RD(RBCP_RD)                    // in    : Read data[7:0]
    );

    IOBUF i_iobuf_mdio(
      .O(mdio_gem_i),
      .IO(ETH_MDIO),
      .I(mdio_gem_o),
      .T(mdio_gem_t));

    wire BUS_WR, BUS_RD;
    wire [31:0] BUS_ADD;
    wire [7:0] BUS_DATA;
    
    rbcp_to_bus irbcp_to_bus(
    
    .BUS_RST(BUS_RST),
    .BUS_CLK(BUS_CLK),
    
    .RBCP_ACT(RBCP_ACT),
    .RBCP_ADDR(RBCP_ADDR),
    .RBCP_WD(RBCP_WD),
    .RBCP_WE(RBCP_WE),
    .RBCP_RE(RBCP_RE),
    .RBCP_ACK(RBCP_ACK),
    .RBCP_RD(RBCP_RD),
    
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA)
  );
    
    //MODULE ADREESSES

    localparam CMD_BASEADDR = 32'h0000;
    localparam CMD_HIGHADDR = 32'h8000-1;

    localparam RX4_BASEADDR = 32'h8300;
    localparam RX4_HIGHADDR = 32'h8400-1;

    localparam RX3_BASEADDR = 32'h8400;
    localparam RX3_HIGHADDR = 32'h8500-1;

    localparam RX2_BASEADDR = 32'h8500;
    localparam RX2_HIGHADDR = 32'h8600-1;

    localparam RX1_BASEADDR = 32'h8600;
    localparam RX1_HIGHADDR = 32'h8700-1;
    
    localparam GPIO_BASEADDR = 32'h8700;
    localparam GPIO_HIGHADDR = 32'h8800-1;

    localparam I2C_BASEADDR = 32'h8800;
    localparam I2C_HIGHADDR = 32'h8900-1; 
        
     
    // MODULES //
    
    cmd_seq #(
        .BASEADDR(CMD_BASEADDR),
        .HIGHADDR(CMD_HIGHADDR),
        .ABUSWIDTH(32)
    ) icmd (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),

        .CMD_CLK_OUT(CMD_CLK),
        .CMD_CLK_IN(CLK_40),
        .CMD_EXT_START_FLAG(1'b0),
        .CMD_EXT_START_ENABLE(),
        .CMD_DATA(CMD_DATA),
        .CMD_READY(),
        .CMD_START_FLAG()
    );
        
    wire [3:0] RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL;
    wire [3:0] FE_FIFO_READ;
    wire [3:0] FE_FIFO_EMPTY;
    wire [31:0] FE_FIFO_DATA [3:0];

    genvar i;
    generate
    for (i = 0; i < 1; i = i + 1) begin: rx_gen
        fei4_rx #(
            .BASEADDR(RX1_BASEADDR-16'h0100*i),
            .HIGHADDR(RX1_HIGHADDR-16'h0100*i),
            .DSIZE(10),
            .DATA_IDENTIFIER(i+1),
            .ABUSWIDTH(32)
        ) i_fei4_rx (
            .RX_CLK(RX_160_CLK),
            .RX_CLK2X(RX_320_CLK),
            .RX_CLK2X_IOCE(RX_320_IOCE),
            .DATA_CLK(RX_16_CLK),

            .RX_DATA(DOBOUT[i]),

            .RX_READY(RX_READY[i]),
            .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR[i]),
            .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR[i]),

            .FIFO_READ(FE_FIFO_READ[i]),
            .FIFO_EMPTY(FE_FIFO_EMPTY[i]),
            .FIFO_DATA(FE_FIFO_DATA[i]),

            .RX_FIFO_FULL(RX_FIFO_FULL[i]),
            .RX_ENABLED(),

            .BUS_CLK(BUS_CLK),
            .BUS_RST(BUS_RST),
            .BUS_ADD(BUS_ADD),
            .BUS_DATA(BUS_DATA),
            .BUS_RD(BUS_RD),
            .BUS_WR(BUS_WR)
        );
    end
    endgenerate
    
    /*
    gpio 
    #( 
        .BASEADDR(GPIO_BASEADDR), 
        .HIGHADDR(GPIO_HIGHADDR),
        .ABUSWIDTH(32),
        .IO_WIDTH(8),
        .IO_DIRECTION(8'h0f)
    ) i_gpio
    (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
        .IO({GPIO_DIP, GPIO_LED})
    );
    */
    
    wire I2C_CLK, I2C_CLK_PRE;
    clock_divider  #( .DIVISOR(4000) ) i2c_clkdev ( .CLK(BUS_CLK), .RESET(BUS_RST), .CE(), .CLOCK(I2C_CLK_PRE) );
    BUFG BUFG_I2C (  .O(I2C_CLK),  .I(I2C_CLK_PRE) );
    
    i2c 
    #( 
        .BASEADDR(I2C_BASEADDR), 
        .HIGHADDR(I2C_HIGHADDR),
        .ABUSWIDTH(32),
        .MEM_BYTES(8) 
    )  i_i2c
    (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
    
        .I2C_CLK(I2C_CLK),
        .I2C_SDA(SDA),
        .I2C_SCL(SCL)
    );
    
    
    //assign FE_FIFO_EMPTY[0] = 1;
    //assign FE_FIFO_EMPTY[1] = 1;
    //assign FE_FIFO_EMPTY[2] = 1;
    //assign FE_FIFO_EMPTY[3] = 1;
    
    wire ARB_READY_OUT, ARB_WRITE_OUT;
    wire [31:0] ARB_DATA_OUT;
    wire [3:0] READ_GRANT;
    
    /*

    rrp_arbiter #(
        .WIDTH(4)
    ) i_rrp_arbiter (
        .RST(BUS_RST),
        .CLK(BUS_CLK),

        .WRITE_REQ({~FE_FIFO_EMPTY}),
        .HOLD_REQ({4'b0}),
        .DATA_IN({FE_FIFO_DATA[3],FE_FIFO_DATA[2],FE_FIFO_DATA[1], FE_FIFO_DATA[0]}),
        .READ_GRANT(READ_GRANT),

        .READY_OUT(ARB_READY_OUT),
        .WRITE_OUT(ARB_WRITE_OUT),
        .DATA_OUT(ARB_DATA_OUT)
    );

    assign FE_FIFO_READ = READ_GRANT[3:0];
    */
    
    
    assign ARB_DATA_OUT = FE_FIFO_DATA[0];
    assign FE_FIFO_READ[0] = ARB_READY_OUT;
    assign ARB_WRITE_OUT = ~FE_FIFO_EMPTY[0];
        
    wire FIFO_EMPTY, FIFO_FULL;
    fifo_32_to_8 #(.DEPTH(1*256)) i_data_fifo (
        .RST(BUS_RST),
        .CLK(BUS_CLK),
        
        .WRITE(ARB_WRITE_OUT),
        .READ(TCP_TX_WR),
        .DATA_IN(ARB_DATA_OUT),
        .FULL(FIFO_FULL),
        .EMPTY(FIFO_EMPTY),
        .DATA_OUT(TCP_TX_DATA)
    );
    assign ARB_READY_OUT = !FIFO_FULL;
    assign TCP_TX_WR = !TCP_TX_FULL && !FIFO_EMPTY;

    assign GPIO_LED = RX_READY;
    
endmodule
