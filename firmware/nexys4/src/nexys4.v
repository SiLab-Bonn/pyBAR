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

module nexys4(
    input wire CLK100MHZ,
    
    output wire ETH_MDC,
    inout wire ETH_MDIO,
    
    output wire ETH_RSTN,
    
    input wire ETH_CRSDV,
    input wire  ETH_RXERR,
    input wire [1:0] ETH_RXD,
    
    output wire ETH_TXEN,
    output wire [1:0] ETH_TXD,
    
    output wire ETH_REFCLK,
    input wire  ETH_INTN,
    
    inout wire SDA, SCL,
        
    output wire CMD_CLK,
    output wire CMD_DATA, 

    input wire [3:0] DOBOUT,
    
    input wire TDC_IN, TDC_TRIG,
    
    input wire TLU_TRG,
    input wire TLU_RST,
    output wire TLU_BSY,
    output wire TLU_CLK,
    
    output wire [4:0] LED
    
);

wire CLK_LOCKED, CLKFBIN, CLKFBOUT;
wire CLKOUT0, CLKOUT1, CLKOUT2, CLKOUT3, CLKOUT4, CLKOUT5;

PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(13),        // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(0.0),      // input wire clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).
    // CLKOUT0_DIVIDE - CLKOUT5_DIVIDE: Divide amount for each CLKOUT (1-128)
    .CLKOUT0_DIVIDE(26),
    .CLKOUT1_DIVIDE(26),
    .CLKOUT2_DIVIDE(32), //40
    .CLKOUT3_DIVIDE(8), //160
    .CLKOUT4_DIVIDE(4), //320
    .CLKOUT5_DIVIDE(80),
    // CLKOUT0_DUTY_CYCLE - CLKOUT5_DUTY_CYCLE: Duty cycle for each CLKOUT (0.001-0.999).
    .CLKOUT0_DUTY_CYCLE(0.5),
    .CLKOUT1_DUTY_CYCLE(0.5),
    .CLKOUT2_DUTY_CYCLE(0.5),
    .CLKOUT3_DUTY_CYCLE(0.5),
    .CLKOUT4_DUTY_CYCLE(0.5),
    .CLKOUT5_DUTY_CYCLE(0.5),
    // CLKOUT0_PHASE - CLKOUT5_PHASE: Phase offset for each CLKOUT (-360.000-360.000).
    .CLKOUT0_PHASE(0.0),
    .CLKOUT1_PHASE(0.0),
    .CLKOUT2_PHASE(0.0),
    .CLKOUT3_PHASE(0.0),
    .CLKOUT4_PHASE(0.0),
    .CLKOUT5_PHASE(0.0),
    .DIVCLK_DIVIDE(1),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input wire jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE")    // Delay DONE until PLL Locks, ("TRUE"/"FALSE")
)
PLLE2_BASE_inst (
    // Clock Outputs: 1-bit (each) output: User configurable clock outputs
    .CLKOUT0(CLKOUT0),   // 1-bit output: CLKOUT0
    .CLKOUT1(CLKOUT1),   // 1-bit output: CLKOUT1
    .CLKOUT2(CLKOUT2),   // 1-bit output: CLKOUT2
    .CLKOUT3(CLKOUT3),   // 1-bit output: CLKOUT3
    .CLKOUT4(CLKOUT4),   // 1-bit output: CLKOUT4
    .CLKOUT5(CLKOUT5),   // 1-bit output: CLKOUT5
    // Feedback Clocks: 1-bit (each) output: Clock feedback ports
    .CLKFBOUT(CLKFBOUT), // 1-bit output: Feedback clock
    .LOCKED(CLK_LOCKED),     // 1-bit output: LOCK
    .CLKIN1(CLK100MHZ),     // 1-bit input wire: input wire clock
    // Control Ports: 1-bit (each) input wire: PLL control ports
    .PWRDWN(1'b0),     // 1-bit input wire: Power-down
    .RST(1'b0),           // 1-bit input wire: Reset
    // Feedback Clocks: 1-bit (each) input wire: Clock feedback ports
    .CLKFBIN(CLKFBIN)    // 1-bit input wire: Feedback clock
);

assign CLKFBIN = CLKFBOUT;
wire ETH_CLK_TX, ETH_CLK_RX;
BUFG BUFG_CLK0 (.I(CLKOUT0), .O(ETH_CLK_TX));
BUFG BUFG_CLK1 (.I(CLKOUT1), .O(ETH_CLK_RX));

(* KEEP = "{TRUE}" *) wire BUS_CLK;
(* KEEP = "{TRUE}" *) wire CLK160;
(* KEEP = "{TRUE}" *) wire CLK320;
(* KEEP = "{TRUE}" *) wire CLK40;
(* KEEP = "{TRUE}" *) wire CLK16;

BUFG BUFG_CLK2 (.I(CLKOUT2), .O(CLK40));
BUFG BUFG_CLK3 (.I(CLKOUT3), .O(CLK160));
BUFG BUFG_CLK4 (.I(CLKOUT4), .O(CLK320));
BUFG BUFG_CLK5 (.I(CLKOUT5), .O(CLK16));

assign ETH_REFCLK = ETH_CLK_TX;
assign BUS_CLK = ETH_CLK_RX;

wire RST;
assign RST = !CLK_LOCKED;

wire EEPROM_CS, EEPROM_SK, EEPROM_DI;
wire TCP_CLOSE_REQ;
wire RBCP_ACT, RBCP_WE, RBCP_RE;
wire [7:0] RBCP_WD, RBCP_RD;
wire [31:0] RBCP_ADDR;
wire TCP_RX_WR;
wire [7:0] TCP_RX_DATA;
wire ETH_TX_ER;
wire RBCP_ACK;
wire TCP_TX_FULL;
wire TCP_TX_WR;
wire [7:0] TCP_TX_DATA;
wire mdio_gem_i;
wire mdio_gem_o;
wire mdio_gem_t;
wire TX_CLK, RX_CLK;
wire BUS_RST;

wire [3:0] ETH_TX_D, ETH_RX_D;
wire ETH_TX_EN, ETH_TX_ER;
wire ETH_COL, ETH_CRS, ETH_RX_DV, ETH_RX_ER;

//50MHz clock
mii_to_rmii_0 imii_to_rmii_0 (
    .rst_n(ETH_RSTN), //IN
    .ref_clk(ETH_CLK_TX), //IN
    
    .mac2rmii_tx_en(ETH_TX_EN), //IN
    .mac2rmii_txd(ETH_TX_D), //IN
    .mac2rmii_tx_er(ETH_TX_ER), //IN
    
    .rmii2mac_tx_clk(TX_CLK), //OUT
    .rmii2mac_rx_clk(RX_CLK), //OUT
    
    .rmii2mac_col(ETH_COL), //OUT
    .rmii2mac_crs(ETH_CRS), //OUT
    .rmii2mac_rx_dv(ETH_RX_DV), //OUT
    .rmii2mac_rx_er(ETH_RX_ER), //OUT
    .rmii2mac_rxd(ETH_RX_D), //OUT
    
    .phy2rmii_crs_dv(ETH_CRSDV), //IN
    .phy2rmii_rx_er(ETH_RXERR), //IN
    .phy2rmii_rxd(ETH_RXD), //IN
    
    .rmii2phy_txd(ETH_TXD), //OUT
    .rmii2phy_tx_en(ETH_TXEN) //OUT
);

wire [3:0] ETH_TX_D_NO;

WRAP_SiTCP_GMII_XC7A_32K #(.TIM_PERIOD(50))sitcp(
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
    .GMII_RSTn(ETH_RSTN)            ,    // out    : PHY reset
    .GMII_1000M(1'b0)            ,    // in    : GMII mode (0:MII, 1:GMII)
    // TX 
    .GMII_TX_CLK(TX_CLK)            ,    // in    : Tx clock
    .GMII_TX_EN(ETH_TX_EN)            ,    // out    : Tx enable
    .GMII_TXD({ETH_TX_D_NO,ETH_TX_D})            ,    // out    : Tx data[7:0]
    .GMII_TX_ER(ETH_TX_ER)            ,    // out    : TX error
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
    .TCP_OPEN_REQ(1'b0)        ,    // in    : Reserved input wire, shoud be 0
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
  .I(mdio_gem_o)
  ,
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

//MODULE ADDRESSES

localparam CMD_BASEADDR = 32'h0000;
localparam CMD_HIGHADDR = 32'h8000-1;

localparam TDC_BASEADDR = 16'h8100;
localparam TDC_HIGHADDR = 16'h8200-1;

localparam TLU_BASEADDR = 16'h8200;
localparam TLU_HIGHADDR = 16'h8300-1;

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
    
///

wire I2C_CLK, I2C_CLK_PRE;
clock_divider  #( .DIVISOR(10000) ) i2c_clkdev ( .CLK(BUS_CLK), .RESET(BUS_RST), .CE(), .CLOCK(I2C_CLK_PRE) );
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


wire [1:0] NOT_CONNECTED_RX;
wire TLU_SEL, TDC_SEL;
wire [3:0] SEL;
gpio #(
    .BASEADDR(GPIO_BASEADDR),
    .HIGHADDR(GPIO_HIGHADDR),
    .ABUSWIDTH(32),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_RX, TDC_SEL, TLU_SEL, SEL[3], SEL[2], SEL[1], SEL[0]})
);

wire CMD_START_FLAG;
wire TRIGGER_ACCEPTED_FLAG;
wire EXT_TRIGGER_ENABLE; // from CMD FSM
wire CMD_READY; // from CMD FSM
wire TRIGGER_ACKNOWLEDGE_FLAG; // to TLU FSM

reg CMD_READY_FF;
always @ (posedge CLK40)
begin
    CMD_READY_FF <= CMD_READY;
end
assign TRIGGER_ACKNOWLEDGE_FLAG = CMD_READY & ~CMD_READY_FF;

cmd_seq 
#( 
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(32),
    .OUTPUTS(1)
) icmd (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CMD_CLK_OUT(CMD_CLK),
    .CMD_CLK_IN(CLK40),
    
    .CMD_EXT_START_FLAG(TRIGGER_ACCEPTED_FLAG),
    .CMD_EXT_START_ENABLE(EXT_TRIGGER_ENABLE),
    .CMD_DATA(CMD_DATA),
    .CMD_READY(CMD_READY),
    .CMD_START_FLAG(CMD_START_FLAG)
    
);

wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
wire [31:0] TIMESTAMP;
wire TRIG_OUT;
wire TDC_OUT;

tdc_s3 #(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .ABUSWIDTH(32),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100),
    .FAST_TDC(1),
    .FAST_TRIGGER(1)
) i_tdc (
    .CLK320(CLK320),
    .CLK160(CLK160),
    .DV_CLK(CLK40),
    .TDC_IN(TDC_IN),
    .TDC_OUT(TDC_OUT),
    .TRIG_IN(TDC_TRIG),
    .TRIG_OUT(TRIG_OUT),

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

wire TRIGGER_FIFO_READ;
wire TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA;
wire TRIGGER_FIFO_PEEMPT_REQ;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .ABUSWIDTH(32),
    .DIVISOR(8),
    .WIDTH(8)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .TRIGGER_CLK(CLK40),
    
    .FIFO_READ(TRIGGER_FIFO_READ),
    .FIFO_EMPTY(TRIGGER_FIFO_EMPTY),
    .FIFO_DATA(TRIGGER_FIFO_DATA),
    
    .FIFO_PREEMPT_REQ(TRIGGER_FIFO_PEEMPT_REQ),
    
    .TRIGGER({6'b0, TDC_OUT, TRIG_OUT}),
    .TRIGGER_VETO({7'b0, FIFO_FULL}),
    
    .EXT_TRIGGER_ENABLE(EXT_TRIGGER_ENABLE),
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),
    
    .TLU_TRIGGER(TLU_TRG),
    .TLU_RESET(TLU_RST),
    .TLU_BUSY(TLU_BSY),
    .TLU_CLOCK(TLU_CLK),
    
    .TIMESTAMP(TIMESTAMP)
);  
    
wire [3:0] RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL, RX_ENABLED;
wire [3:0] FE_FIFO_READ;
wire [3:0] FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA [3:0];

genvar i;
generate
for (i = 0; i < 4; i = i + 1) begin: rx_gen
    fei4_rx #(
        .BASEADDR(RX1_BASEADDR-16'h0100*i),
        .HIGHADDR(RX1_HIGHADDR-16'h0100*i),
        .DSIZE(10),
        .DATA_IDENTIFIER(i+1),
        .ABUSWIDTH(32)
    ) i_fei4_rx (
        .RX_CLK(CLK160),
        .RX_CLK2X(CLK320),
        .DATA_CLK(CLK16),

        .RX_DATA(DOBOUT[i]),

        .RX_READY(RX_READY[i]),
        .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR[i]),
        .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR[i]),

        .FIFO_READ(FE_FIFO_READ[i]),
        .FIFO_EMPTY(FE_FIFO_EMPTY[i]),
        .FIFO_DATA(FE_FIFO_DATA[i]),

        .RX_FIFO_FULL(RX_FIFO_FULL[i]),
        .RX_ENABLED(RX_ENABLED[i]),

        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
    );
end
endgenerate

wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [5:0] READ_GRANT;
 
rrp_arbiter #(
    .WIDTH(6)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),
    .WRITE_REQ({~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY & TDC_SEL, ~TRIGGER_FIFO_EMPTY & TLU_SEL}),
    .HOLD_REQ({5'b0, TRIGGER_FIFO_PEEMPT_REQ}),
    .DATA_IN({FE_FIFO_DATA[3],FE_FIFO_DATA[2],FE_FIFO_DATA[1], FE_FIFO_DATA[0], TDC_FIFO_DATA, TRIGGER_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),
    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign FE_FIFO_READ = READ_GRANT[5:2];
assign TDC_FIFO_READ = READ_GRANT[1];
assign TRIGGER_FIFO_READ = READ_GRANT[0];
    
wire FIFO_EMPTY, FIFO_FULL;
fifo_32_to_8 #(.DEPTH(64*1024)) i_data_fifo (
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

//assign GPIO_LED = RX_READY;

wire CE_1HZ; 
wire CLK_1HZ; 
clock_divider #(
    .DIVISOR(40000000)
) i_clock_divisor_40MHz_to_1Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(CE_1HZ),
    .CLOCK(CLK_1HZ)
);

wire CLK_3HZ;
clock_divider #(
    .DIVISOR(13333333)
) i_clock_divisor_40MHz_to_3Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_3HZ)
);

assign LED[0] = (RX_ENABLED[0] & RX_READY[0]) & ((RX_8B10B_DECODER_ERR[0]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[0] | RX_FIFO_FULL[0]);
assign LED[1] = (RX_ENABLED[1] & RX_READY[1]) & ((RX_8B10B_DECODER_ERR[1]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[1] | RX_FIFO_FULL[1]);
assign LED[2] = (RX_ENABLED[2] & RX_READY[2]) & ((RX_8B10B_DECODER_ERR[2]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[2] | RX_FIFO_FULL[2]);
assign LED[3] = (RX_ENABLED[3] & RX_READY[3]) & ((RX_8B10B_DECODER_ERR[3]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[3] | RX_FIFO_FULL[3]);
assign LED[4] = (CLK_1HZ | FIFO_FULL) & CLK_LOCKED;

endmodule
