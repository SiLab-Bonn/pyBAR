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

module mmc3_16chip_multi_tx_eth(
    input wire RESET_N,
    input wire clkin,
    output wire [3:0] rgmii_txd,
    output wire rgmii_tx_ctl,
    output wire rgmii_txc,
    input wire [3:0] rgmii_rxd,
    input wire rgmii_rx_ctl,
    input wire rgmii_rxc,
    output wire mdio_phy_mdc,
    inout wire mdio_phy_mdio,
    output wire phy_rst_n,
    output wire [7:0] LED,
    output wire [7:0] CMD_CLK_P, CMD_CLK_N,
    output wire [7:0] CMD_DATA_P, CMD_DATA_N,
    input wire [0:0] RJ45_HITOR_N, RJ45_HITOR_P,
    input wire [15:0] DOBOUT_N, DOBOUT_P,
    output wire RJ45_BUSY_LEMO_TX1, RJ45_CLK_LEMO_TX0,
    input wire RJ45_TRIGGER, RJ45_RESET,
    input wire [1:0] LEMO_RX
);


wire RST;
wire CLK250PLL, CLK125PLLTX, CLK125PLLTX90, CLK125PLLRX;
wire PLL_FEEDBACK, LOCKED;

PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(10),       // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(10.000),      // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).

    .CLKOUT0_DIVIDE(7),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT0_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT0_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT1_DIVIDE(4),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT1_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT1_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT2_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT2_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT2_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT3_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT3_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT3_PHASE(90.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT4_DIVIDE(8),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT4_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT4_PHASE(-5.6),      // Phase offset for CLKOUT0 (-360.000-360.000).
    //-65 -> 0?; - 45 -> 39;  -25 -> 100; -5 -> 0;

    .DIVCLK_DIVIDE(1),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE")     // Delay DONE until PLL Locks, ("TRUE"/"FALSE")
 )
 PLLE2_BASE_inst (

     .CLKOUT0(),
     .CLKOUT1(CLK250PLL),

     .CLKOUT2(CLK125PLLTX),
     .CLKOUT3(CLK125PLLTX90),
     .CLKOUT4(CLK125PLLRX),

     .CLKOUT5(),

     .CLKFBOUT(PLL_FEEDBACK),

     .LOCKED(LOCKED),     // 1-bit output: LOCK

     // Input 100 MHz clock
     .CLKIN1(clkin),

     // Control Ports
     .PWRDWN(0),
     .RST(!RESET_N),

     // Feedback
     .CLKFBIN(PLL_FEEDBACK)
 );

wire PLL_FEEDBACK2, LOCKED2;
wire CLK160_PLL, CLK320_PLL, CLK40_PLL, CLK16_PLL, BUS_CLK_PLL, CLK200_PLL;
PLLE2_BASE #(
     .BANDWIDTH("OPTIMIZED"),
     .CLKFBOUT_MULT(16),
     .CLKFBOUT_PHASE(0.0),
     .CLKIN1_PERIOD(10.000),

     .CLKOUT0_DIVIDE(10),
     .CLKOUT0_DUTY_CYCLE(0.5),
     .CLKOUT0_PHASE(0.0),

     .CLKOUT1_DIVIDE(40),
     .CLKOUT1_DUTY_CYCLE(0.5),
     .CLKOUT1_PHASE(0.0),

     .CLKOUT2_DIVIDE(5),
     .CLKOUT2_DUTY_CYCLE(0.5),
     .CLKOUT2_PHASE(0.0),

     .CLKOUT3_DIVIDE(100),
     .CLKOUT3_DUTY_CYCLE(0.5),
     .CLKOUT3_PHASE(0.0),

     .CLKOUT4_DIVIDE(12),
     .CLKOUT4_DUTY_CYCLE(0.5),
     .CLKOUT4_PHASE(0.0),

     .CLKOUT5_DIVIDE(8),
     .CLKOUT5_DUTY_CYCLE(0.5),
     .CLKOUT5_PHASE(0.0),


     .DIVCLK_DIVIDE(1),
     .REF_JITTER1(0.0),
     .STARTUP_WAIT("FALSE")
)
PLLE2_BASE_inst_2 (

      .CLKOUT0(CLK160_PLL),
      .CLKOUT1(CLK40_PLL),
      .CLKOUT2(CLK320_PLL),
      .CLKOUT3(CLK16_PLL),
      .CLKOUT4(BUS_CLK_PLL),
      .CLKOUT5(CLK200_PLL),

      .CLKFBOUT(PLL_FEEDBACK2),
      .LOCKED(LOCKED2),     // 1-bit output: LOCK

      .CLKIN1(clkin),

      .PWRDWN(0),
      .RST(!RESET_N),

      .CLKFBIN(PLL_FEEDBACK2)
);


wire CLK160, CLK40, CLK320, CLK16, BUS_CLK, CLK200;
BUFG BUFG_inst_160 (.O(CLK160), .I(CLK160_PLL) );
BUFG BUFG_inst_40 (.O(CLK40), .I(CLK40_PLL) );
BUFG BUFG_inst_320 (.O(CLK320), .I(CLK320_PLL) );
BUFG BUFG_inst_16 (.O(CLK16), .I(CLK16_PLL) );
BUFG BUFG_inst_BUS_CLK (.O(BUS_CLK), .I(BUS_CLK_PLL) );
BUFG BUFG_inst_200 (.O(CLK200), .I(CLK200_PLL) );
//assign BUS_CLK = CLK160;

wire IDELAYCTRL_RDY;
IDELAYCTRL IDELAYCTRL_inst (
  .RDY(IDELAYCTRL_RDY),
  .REFCLK(CLK200),
  .RST(!LOCKED2)
);


wire CLK125TX, CLK125TX90, CLK125RX;
BUFG BUFG_inst_CLK125TX (  .O(CLK125TX),  .I(CLK125PLLTX) );
BUFG BUFG_inst_CLK125TX90 (  .O(CLK125TX90),  .I(CLK125PLLTX90) );
BUFG BUFG_inst_CLK125RX (  .O(CLK125RX),  .I(rgmii_rxc) );

assign RST = !RESET_N | !LOCKED | !LOCKED2;


wire   gmii_tx_clk;
wire   gmii_tx_en;
wire  [7:0] gmii_txd;
wire   gmii_tx_er;
wire   gmii_crs;
wire   gmii_col;
wire   gmii_rx_clk;
wire   gmii_rx_dv;
wire  [7:0] gmii_rxd;
wire   gmii_rx_er;
wire   mdio_gem_mdc;
wire   mdio_gem_i;
wire   mdio_gem_o;
wire   mdio_gem_t;
wire   link_status;
wire  [1:0] clock_speed;
wire   duplex_status;

rgmii_io rgmii
(
    .rgmii_txd(rgmii_txd),
    .rgmii_tx_ctl(rgmii_tx_ctl),
    .rgmii_txc(rgmii_txc),

    .rgmii_rxd(rgmii_rxd),
    .rgmii_rx_ctl(rgmii_rx_ctl),

    .gmii_txd_int(gmii_txd),      // Internal gmii_txd signal.
    .gmii_tx_en_int(gmii_tx_en),
    .gmii_tx_er_int(gmii_tx_er),
    .gmii_col_int(gmii_col),
    .gmii_crs_int(gmii_crs),
    .gmii_rxd_reg(gmii_rxd),   // RGMII double data rate data valid.
    .gmii_rx_dv_reg(gmii_rx_dv), // gmii_rx_dv_ibuf registered in IOBs.
    .gmii_rx_er_reg(gmii_rx_er), // gmii_rx_er_ibuf registered in IOBs.

    .eth_link_status(link_status),
    .eth_clock_speed(clock_speed),
    .eth_duplex_status(duplex_status),

                              // FOllowing are generated by DCMs
    .tx_rgmii_clk_int(CLK125TX),     // Internal RGMII transmitter clock.
    .tx_rgmii_clk90_int(CLK125TX90),   // Internal RGMII transmitter clock w/ 90 deg phase
    .rx_rgmii_clk_int(CLK125RX),     // Internal RGMII receiver clock

    .reset(!phy_rst_n)
);

// Instantiate tri-state buffer for MDIO
IOBUF i_iobuf_mdio(
    .O(mdio_gem_i),
    .IO(mdio_phy_mdio),
    .I(mdio_gem_o),
    .T(mdio_gem_t));

wire EEPROM_CS, EEPROM_SK, EEPROM_DI;
wire TCP_CLOSE_REQ;
wire RBCP_ACT, RBCP_WE, RBCP_RE;
wire [7:0] RBCP_WD, RBCP_RD;
wire [31:0] RBCP_ADDR;
wire TCP_RX_WR;
wire [7:0] TCP_RX_DATA;
wire RBCP_ACK;
wire SiTCP_RST;

wire TCP_TX_FULL;
wire TCP_TX_WR;
wire [7:0] TCP_TX_DATA;


WRAP_SiTCP_GMII_XC7K_32K sitcp(
    .CLK(BUS_CLK)                    ,    // in    : System Clock >129MHz
    .RST(RST)                    ,    // in    : System reset
    // Configuration parameters
    .FORCE_DEFAULTn(1'b0)        ,    // in    : Load default parameters
    .EXT_IP_ADDR(32'hc0a80b11)            ,    // in    : IP address[31:0] //192.168.10.16
    .EXT_TCP_PORT(16'd24)        ,    // in    : TCP port #[15:0]
    .EXT_RBCP_PORT(16'd4660)        ,    // in    : RBCP port #[15:0]
    .PHY_ADDR(5'd3)            ,    // in    : PHY-device MIF address[4:0]
    // EEPROM
    .EEPROM_CS(EEPROM_CS)            ,    // out    : Chip select
    .EEPROM_SK(EEPROM_SK)            ,    // out    : Serial data clock
    .EEPROM_DI(EEPROM_DI)            ,    // out    : Serial write data
    .EEPROM_DO(1'b0)            ,    // in    : Serial read data
    // user data, intialial values are stored in the EEPROM, 0xFFFF_FC3C-3F
    .USR_REG_X3C()            ,    // out    : Stored at 0xFFFF_FF3C
    .USR_REG_X3D()            ,    // out    : Stored at 0xFFFF_FF3D
    .USR_REG_X3E()            ,    // out    : Stored at 0xFFFF_FF3E
    .USR_REG_X3F()            ,    // out    : Stored at 0xFFFF_FF3F
    // MII interface
    .GMII_RSTn(phy_rst_n)            ,    // out    : PHY reset
    .GMII_1000M(1'b1)            ,    // in    : GMII mode (0:MII, 1:GMII)
    // TX
    .GMII_TX_CLK(CLK125TX)            ,    // in    : Tx clock
    .GMII_TX_EN(gmii_tx_en)            ,    // out    : Tx enable
    .GMII_TXD(gmii_txd)            ,    // out    : Tx data[7:0]
    .GMII_TX_ER(gmii_tx_er)            ,    // out    : TX error
    // RX
    .GMII_RX_CLK(CLK125RX)           ,    // in    : Rx clock
    .GMII_RX_DV(gmii_rx_dv)            ,    // in    : Rx data valid
    .GMII_RXD(gmii_rxd)            ,    // in    : Rx data[7:0]
    .GMII_RX_ER(gmii_rx_er)            ,    // in    : Rx error
    .GMII_CRS(gmii_crs)            ,    // in    : Carrier sense
    .GMII_COL(gmii_col)            ,    // in    : Collision detected
    // Management IF
    .GMII_MDC(mdio_phy_mdc)            ,    // out    : Clock for MDIO
    .GMII_MDIO_IN(mdio_gem_i)        ,    // in    : Data
    .GMII_MDIO_OUT(mdio_gem_o)        ,    // out    : Data
    .GMII_MDIO_OE(mdio_gem_t)        ,    // out    : MDIO output enable
    // User I/F
    .SiTCP_RST(SiTCP_RST)            ,    // out    : Reset for SiTCP and related circuits
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

// -------  BUS SIGNALLING  ------- //

wire BUS_WR, BUS_RD, BUS_RST;
wire [31:0] BUS_ADD;
wire [7:0] BUS_DATA;
assign BUS_RST = SiTCP_RST;

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

// -------  MODULE ADDRESSES  ------- //

localparam CMD_BASEADDR = 32'h0000;
localparam CMD_HIGHADDR = 32'h8000-1;

localparam TLU_BASEADDR = 32'h40000;
localparam TLU_HIGHADDR = 32'h40100-1;

localparam RX_BASEADDR = 32'h41000;
localparam RX_HIGHADDR = 32'h41100-1;

localparam TDC_BASEADDR = 32'h42fff;
localparam TDC_HIGHADDR = 32'h430ff-1;

localparam GPIO_DLY_BASEADDR = 32'h450ef;
localparam GPIO_DLY_HIGHADDR = 32'h651ef-1;



// -------  USER MODULES  ------- //
wire [47:0] GPIO_DLY_IO;

gpio
#(
    .BASEADDR(GPIO_DLY_BASEADDR),
    .HIGHADDR(GPIO_DLY_HIGHADDR),
    .IO_WIDTH(48),
    .IO_DIRECTION(48'hffffffffffff),
    .IO_TRI(48'h000000000000),
    .ABUSWIDTH(32)
) i_gpio
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(GPIO_DLY_IO)
);
wire [4:0] IDELAYE_CINVCTRL;
wire [4:0] IDELAYE_LD;
wire [4:0] IDELAYE_CNTVALUEIN [4:0];
wire [2:0] SEL_CLK40;

assign IDELAYE_LD[0] = GPIO_DLY_IO[7];
assign IDELAYE_CINVCTRL[0] = GPIO_DLY_IO[6];
assign IDELAYE_CNTVALUEIN[0] = GPIO_DLY_IO[4:0];
assign IDELAYE_LD[1] = GPIO_DLY_IO[7+1*8];
assign IDELAYE_CINVCTRL[1] = GPIO_DLY_IO[6+1*8];
assign IDELAYE_CNTVALUEIN[1] = GPIO_DLY_IO[4+1*8:0+1*8];
assign IDELAYE_LD[2] = GPIO_DLY_IO[7+2*8];
assign IDELAYE_CINVCTRL[2] = GPIO_DLY_IO[6+2*8];
assign IDELAYE_CNTVALUEIN[2] = GPIO_DLY_IO[4+2*8:0+2*8];
assign IDELAYE_LD[3] = GPIO_DLY_IO[7+3*8];
assign IDELAYE_CINVCTRL[3] = GPIO_DLY_IO[6+3*8];
assign IDELAYE_CNTVALUEIN[3] = GPIO_DLY_IO[4+3*8:0+3*8];
assign IDELAYE_LD[4] = GPIO_DLY_IO[7+4*8];
assign IDELAYE_CINVCTRL[4] = GPIO_DLY_IO[6+4*8];
assign IDELAYE_CNTVALUEIN[4] = GPIO_DLY_IO[4+4*8:0+4*8];
assign SEL_CLK40 = GPIO_DLY_IO[42:40];

wire [7:0] CMD_DATA, CMD_CLK;

wire [7:0] TRIGGER_ENABLE; // from CMD FSM
wire [7:0] CMD_READY; // from CMD FSM
wire [7:0] CMD_START_FLAG;
wire [7:0] TRIGGER_ACCEPTED_FLAG;
wire [7:0] CMD_EXT_START_FLAG;
assign CMD_EXT_START_FLAG = TRIGGER_ACCEPTED_FLAG;
wire [7:0] EXT_TRIGGER_ENABLE;

reg [7:0] CLK_SR;
reg CLK40_OUT_SEL;
always@(posedge CLK320)
    CLK_SR <= {CLK_SR[6:0],CLK40};

always@(posedge CLK320)
    CLK40_OUT_SEL <= CLK_SR[SEL_CLK40];

wire BROADCAST_CMD;
genvar h;
generate
  for (h = 0; h < 8; h = h + 1) begin: cmd_gen
  cmd_seq #(
        .BASEADDR(CMD_BASEADDR+32'h8000*h),
        .HIGHADDR(CMD_HIGHADDR+32'h8000*h),
        .ABUSWIDTH(32),
        .OUTPUTS(1)
    ) i_cmd_seq (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),

        .CMD_CLK_IN(CLK40),
        .CMD_CLK_OUT(CMD_CLK[h]),
        .CMD_DATA(CMD_DATA[h]),

        .CMD_EXT_START_FLAG(BROADCAST_CMD ? CMD_EXT_START_FLAG[0] : CMD_EXT_START_FLAG[h]),
        .CMD_EXT_START_ENABLE(EXT_TRIGGER_ENABLE[h]),
        .CMD_READY(CMD_READY[h]),
        .CMD_START_FLAG(CMD_START_FLAG[h])
    );

    OBUFDS #(
      .IOSTANDARD("LVDS_25"),
      .SLEW("SLOW")
    ) OBUFDS_inst_cmd_clk_out_h (
      .O(CMD_CLK_P[h]),
      .OB(CMD_CLK_N[h]),
      .I(CLK40_OUT_SEL)
  //.I(CMD_CLK)
  );

    OBUFDS #(
    .IOSTANDARD("LVDS_25"),
    .SLEW("SLOW")
  ) OBUFDS_inst_cmd_data_h (
    .O(CMD_DATA_P[h]),
    .OB(CMD_DATA_N[h]),
    .I(CMD_DATA[h])
//.I(CMD_CLK)

    );
  end
endgenerate

wire [7:0] TRIGGER_ACKNOWLEDGE_FLAG; // to TLU FSM
reg [7:0] CMD_READY_FF;
always @ (posedge CLK40)
begin
    CMD_READY_FF <= CMD_READY;
end
assign TRIGGER_ACKNOWLEDGE_FLAG = CMD_READY & ~CMD_READY_FF;

reg CMD_READY_BROADCAST;
always @ (posedge CLK40)
begin
  if (!BROADCAST_CMD)
    CMD_READY_BROADCAST <= 1'b0;
  else if (~&(CMD_READY | (~EXT_TRIGGER_ENABLE)))
    CMD_READY_BROADCAST <= 1'b0;
  else if (&(CMD_READY | (~EXT_TRIGGER_ENABLE)))
    CMD_READY_BROADCAST <= 1'b1;
  else
    CMD_READY_BROADCAST <= CMD_READY_BROADCAST;
end

wire CMD_READY_BROADCAST_FLAG;
reg CMD_READY_BROADCAST_FF;
always @ (posedge CLK40)
begin
    CMD_READY_BROADCAST_FF <= CMD_READY_BROADCAST;
end
assign CMD_READY_BROADCAST_FLAG = CMD_READY_BROADCAST & ~CMD_READY_BROADCAST_FF;

wire [7:0] TRIGGER_FIFO_READ;
wire [7:0] TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA [7:0];
wire [7:0] TRIGGER_FIFO_PREEMPT_REQ;
wire [31:0] TIMESTAMP [7:0];
wire [0:0] TDC_OUT;
wire [15:0] RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL, RX_ENABLED;
wire FIFO_FULL;
wire TLU_BUSY, TLU_CLOCK;
wire [7:0] TRIGGER_ENABLED, TLU_ENABLED;
wire [7:0] TRIGGER_SELECTED [7:0];
assign RJ45_BUSY_LEMO_TX1 = TLU_ENABLED[0] ? TLU_BUSY : ~CMD_READY_BROADCAST;
assign RJ45_CLK_LEMO_TX0 = TLU_CLOCK;

genvar k;
generate
  for (k = 1; k < 8; k = k + 1) begin: tlu_gen
    tlu_controller #(
        .BASEADDR(TLU_BASEADDR+32'h0100*k),
        .HIGHADDR(TLU_HIGHADDR+32'h0100*k),
        .DIVISOR(8),
        .ABUSWIDTH(32),
        .WIDTH(9)
    ) i_tlu_controller (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),

        .TRIGGER_CLK(CLK40),

        .FIFO_READ(TRIGGER_FIFO_READ[k]),
        .FIFO_EMPTY(TRIGGER_FIFO_EMPTY[k]),
        .FIFO_DATA(TRIGGER_FIFO_DATA[k]),

        .FIFO_PREEMPT_REQ(TRIGGER_FIFO_PREEMPT_REQ[k]),

        .TRIGGER_ENABLED(TRIGGER_ENABLED[k]),
        .TRIGGER_SELECTED(TRIGGER_SELECTED[k]),
        .TLU_ENABLED(TLU_ENABLED[k]),

        .TRIGGER({TDC_OUT, LEMO_RX[0]}),
        .TRIGGER_VETO({RX_FIFO_FULL, FIFO_FULL}),
        .TIMESTAMP_RESET(1'b0),

        .EXT_TRIGGER_ENABLE(BROADCAST_CMD ? 1'b0 : EXT_TRIGGER_ENABLE[k]),
        .TRIGGER_ACKNOWLEDGE(BROADCAST_CMD ? 1'b0 : TRIGGER_ACKNOWLEDGE_FLAG[k]),
        .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG[k]),

        .TLU_TRIGGER(1'b0),
        .TLU_RESET(1'b0),
        .TLU_BUSY(),
        .TLU_CLOCK(),

        .TIMESTAMP(TIMESTAMP[k])
    );
  end
endgenerate

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
    .ABUSWIDTH(32),
    .WIDTH(9)
) i_tlu_controller_0 (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TRIGGER_CLK(CLK40),

    .FIFO_READ(TRIGGER_FIFO_READ[0]),
    .FIFO_EMPTY(TRIGGER_FIFO_EMPTY[0]),
    .FIFO_DATA(TRIGGER_FIFO_DATA[0]),

    .FIFO_PREEMPT_REQ(TRIGGER_FIFO_PREEMPT_REQ[0]),

    .TRIGGER_ENABLED(TRIGGER_ENABLED[0]),
    .TRIGGER_SELECTED(TRIGGER_SELECTED[0]),
    .TLU_ENABLED(TLU_ENABLED[0]),

    .TRIGGER({TDC_OUT, LEMO_RX[0]}),
    .TRIGGER_VETO({RX_FIFO_FULL, FIFO_FULL}),
    .TIMESTAMP_RESET(1'b0),

    .EXT_TRIGGER_ENABLE(BROADCAST_CMD ? |EXT_TRIGGER_ENABLE : EXT_TRIGGER_ENABLE[0]),
    .TRIGGER_ACKNOWLEDGE(BROADCAST_CMD ? CMD_READY_BROADCAST_FLAG : TRIGGER_ACKNOWLEDGE_FLAG[0]),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG[0]),

    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),

    .TIMESTAMP(TIMESTAMP[0])
);
assign BROADCAST_CMD = (TRIGGER_ENABLED == 8'b0000_0001 && (TLU_ENABLED[0] || TRIGGER_SELECTED[0] == 8'b0000_0001));


wire [15:0] FE_FIFO_READ;
wire [15:0] FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA [15:0];

wire [0:0] TDC_FIFO_READ;
wire [0:0] TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA [0:0];

genvar i;
generate
  for (i = 0; i < 16; i = i + 1) begin: rx_gen
    wire DOBOUT;
    reg DOBOUT_DLY;
    fei4_rx #(
        .BASEADDR(RX_BASEADDR+32'h0100*i),
        .HIGHADDR(RX_HIGHADDR+32'h0100*i),
        .DSIZE(10),
        .DATA_IDENTIFIER(i),
        .ABUSWIDTH(32)
    ) i_fei4_rx (
        .RX_CLK(CLK160),
        .RX_CLK2X(CLK320),
        .DATA_CLK(CLK16),

        .RX_DATA(DOBOUT_DLY),

        .RX_READY(RX_READY[i]),
        .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR[i]),
        .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR[i]),

        .FIFO_CLK(1'b0),
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

    IBUFDS #(
        .DIFF_TERM("TRUE"),
        .IBUF_LOW_PWR("FALSE"),
        .IOSTANDARD("LVDS_25")
    ) IBUFDS_inst_i (
        .O(DOBOUT),
        .I(DOBOUT_P[i]),
        .IB(DOBOUT_N[i])
    );

    always@(*) DOBOUT_DLY = DOBOUT;
end
endgenerate

wire [0:0] RJ45_HITOR;

genvar j;
generate
  for (j = 0; j < 1; j = j + 1) begin: tdc_gen
        tdc_s3 #(
        .BASEADDR(TDC_BASEADDR+32'h0100*j),
        .HIGHADDR(TDC_HIGHADDR+32'h0100*j),
        .ABUSWIDTH(32),
        .CLKDV(4),
        .DATA_IDENTIFIER(4'b0001 + j),
        .FAST_TDC(1),
        .FAST_TRIGGER(0)
    ) i_tdc (
        .CLK320(CLK320),
        .CLK160(CLK160),
        .DV_CLK(CLK40),
        .TDC_IN(RJ45_HITOR[j]),
        .TDC_OUT(TDC_OUT[j]),
        .TRIG_IN(),
        .TRIG_OUT(),

        .FIFO_READ(TDC_FIFO_READ[j]),
        .FIFO_EMPTY(TDC_FIFO_EMPTY[j]),
        .FIFO_DATA(TDC_FIFO_DATA[j]),

        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),

        .ARM_TDC(CMD_START_FLAG[j]), // arm TDC by sending commands
        .EXT_EN(1'b0),

        .TIMESTAMP(TIMESTAMP[j][15:0])
    );

    IBUFDS #(
        .DIFF_TERM("TRUE"),
        .IBUF_LOW_PWR("FALSE"),
        .IOSTANDARD("LVDS_25")
    ) IBUFDS_inst_RJ45_HITOR (
        .O(RJ45_HITOR[j]),
        .I(RJ45_HITOR_P[j]),
        .IB(RJ45_HITOR_N[j])
    );

  end
endgenerate


wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [24:0] READ_GRANT;

rrp_arbiter #(
    .WIDTH(24)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TDC_FIFO_EMPTY, ~FE_FIFO_EMPTY, ~TRIGGER_FIFO_EMPTY}),
    .HOLD_REQ({17'b0, TRIGGER_FIFO_PREEMPT_REQ}),
    .DATA_IN({TDC_FIFO_DATA[0], FE_FIFO_DATA[15], FE_FIFO_DATA[14], FE_FIFO_DATA[13], FE_FIFO_DATA[12], FE_FIFO_DATA[11], FE_FIFO_DATA[10], FE_FIFO_DATA[9], FE_FIFO_DATA[8], FE_FIFO_DATA[7], FE_FIFO_DATA[6], FE_FIFO_DATA[5], FE_FIFO_DATA[4], FE_FIFO_DATA[3], FE_FIFO_DATA[2], FE_FIFO_DATA[1], FE_FIFO_DATA[0], TRIGGER_FIFO_DATA[7], TRIGGER_FIFO_DATA[6], TRIGGER_FIFO_DATA[5], TRIGGER_FIFO_DATA[4], TRIGGER_FIFO_DATA[3], TRIGGER_FIFO_DATA[2], TRIGGER_FIFO_DATA[1], TRIGGER_FIFO_DATA[0]}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TRIGGER_FIFO_READ = READ_GRANT[7:0];
assign FE_FIFO_READ = READ_GRANT[23:8];
assign TDC_FIFO_READ = READ_GRANT[24:24];

//cdc_fifo is for timing reasons
wire [31:0] cdc_data_out;
wire full_32to8, cdc_fifo_empty;
wire FIFO_EMPTY;
cdc_syncfifo #(.DSIZE(32), .ASIZE(3)) cdc_syncfifo_i
(
    .rdata(cdc_data_out),
    .wfull(FIFO_FULL),
    .rempty(cdc_fifo_empty),
    .wdata(ARB_DATA_OUT),
    .winc(ARB_WRITE_OUT), .wclk(BUS_CLK), .wrst(BUS_RST),
    .rinc(!full_32to8), .rclk(BUS_CLK), .rrst(BUS_RST)
);
assign ARB_READY_OUT = !FIFO_FULL;

fifo_32_to_8 #(.DEPTH(256*1024)) i_data_fifo (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE(!cdc_fifo_empty),
    .READ(TCP_TX_WR),
    .DATA_IN(cdc_data_out),
    .FULL(full_32to8),
    .EMPTY(FIFO_EMPTY),
    .DATA_OUT(TCP_TX_DATA)
);

assign TCP_TX_WR = !TCP_TX_FULL && !FIFO_EMPTY;

wire CLK_1HZ;
clock_divider #(
    .DIVISOR(40000000)
) i_clock_divisor_40MHz_to_1Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(),
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




assign LED[7:4] = 4'hf;
assign LED[0] = ~((CLK_1HZ | FIFO_FULL) & LOCKED & LOCKED2);
assign LED[1] = ~((((RX_READY != RX_ENABLED) || |(RX_8B10B_DECODER_ERR & RX_ENABLED))? CLK_3HZ : CLK_1HZ) | (|(RX_FIFO_OVERFLOW_ERR & RX_ENABLED)) | (|(RX_FIFO_FULL & RX_ENABLED)));
assign LED[2] = 1'b1;
assign LED[3] = 1'b1;



endmodule
