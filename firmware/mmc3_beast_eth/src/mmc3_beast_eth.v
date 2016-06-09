

module mmc3_m26_eth(
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
    
    output wire CMD_CLK_P, CMD_CLK_N,
    output wire CMD_DATA_P, CMD_DATA_N,
    input wire RJ45_HITOR_N, RJ45_HITOR_P,
    input wire DOBOUT_N, DOBOUT_P,
    
    input wire [5:0] M26_CLK_P, M26_CLK_N, M26_MKD_P, M26_MKD_N,
    input wire [5:0] M26_DATA1_P, M26_DATA1_N, M26_DATA0_P, M26_DATA0_N,
    
    output wire M26_TCK_P,M26_TCK_N,
    output wire M26_TMS_P,M26_TMS_N,
    output wire M26_TDI_P,M26_TDI_N,
    input wire M26_TDO_P,M26_TDO_N,
    
    
    output wire RJ45_BUSY_LEMO_TX1, RJ45_CLK_LEMO_TX0, 
    input wire RJ45_TRIGGER, RJ45_RESET,
    input wire [1:0] LEMO_RX

);


wire RST;
wire BUS_CLK_PLL, CLK250PLL, CLK125PLLTX, CLK125PLLTX90, CLK125PLLRX;
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
wire CLK160_PLL, CLK320_PLL, CLK40_PLL, CLK16_PLL, BUS_CLK_PLL;
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
      .CLKOUT5(),
      
      .CLKFBOUT(PLL_FEEDBACK2),
      .LOCKED(LOCKED2),     // 1-bit output: LOCK
      
      .CLKIN1(clkin),
     
      .PWRDWN(0),
      .RST(!RESET_N),

      .CLKFBIN(PLL_FEEDBACK2)
);
  

wire CLK160, CLK40, CLK320, CLK16, BUS_CLK;
BUFG BUFG_inst_160 (.O(CLK160), .I(CLK160_PLL) );
BUFG BUFG_inst_40 (.O(CLK40), .I(CLK40_PLL) );
BUFG BUFG_inst_320 (.O(CLK320), .I(CLK320_PLL) );
BUFG BUFG_inst_16 (.O(CLK16), .I(CLK16_PLL) );
BUFG BUFG_inst_BUS_CLK (.O(BUS_CLK), .I(BUS_CLK_PLL) );
//assign BUS_CLK = CLK160;

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
    .EXT_IP_ADDR(32'hc0a80a10)            ,    // in    : IP address[31:0] //192.168.10.16
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

// -------  BUS SYGNALING  ------- //
 
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

// -------  MODULE ADREESSES  ------- //

localparam CMD_BASEADDR = 32'h0000;
localparam CMD_HIGHADDR = 32'h8000-1;

localparam TLU_BASEADDR = 32'h8200;
localparam TLU_HIGHADDR = 32'h8300-1;

localparam RX_BASEADDR = 32'h8600;
localparam RX_HIGHADDR = 32'h8700-1;

localparam TDC_BASEADDR = 32'h8700;
localparam TDC_HIGHADDR = 32'h8800-1;

localparam GPIO_BASEADDR = 32'hb000;
localparam GPIO_HIGHADDR = 32'hb01f;

    
// -------  USER MODULES  ------- //
///////////////////// M26 JTAG
wire M26_TCK, M26_TMS,M26_TDI,M26_TDO,M26_TMS_INV,M26_TDI_INV, M26_TDO_INV;
wire M26_RESETB;
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW") 
) OBUFDS_inst_m26_tck (
  .O(M26_TCK_P),
  .OB(M26_TCK_N), 
  .I(M26_TCK)    
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW") 
) OBUFDS_inst_m26_tms (
  .O(M26_TMS_P),
  .OB(M26_TMS_N), 
  .I(M26_TMS)    
);
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW") 
) OBUFDS_inst_m26_tdi (
  .O(M26_TDI_P),
  .OB(M26_TDI_N), 
  .I(M26_TDI)    
);
IBUFDS #(
    .DIFF_TERM("TRUE"), 
    .IBUF_LOW_PWR("FALSE"), 
    .IOSTANDARD("LVDS_25") 
) IBUFDS_inst_m26_tdo (
    .O(M26_TDO), 
    .I(M26_TDO_P),  
    .IB(M26_TDO_N)
);
assign M26_TMS= ~M26_TMS_INV;
assign M26_TDI= ~M26_TDI_INV;
assign M26_TDO_INV = ~M26_TDO;

gpio #(
    .BASEADDR(GPIO_BASEADDR),
    .HIGHADDR(GPIO_HIGHADDR),
    .ABUSWIDTH(32),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hef)
) i_gpio_jtag (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({LED[5:3],M26_TDO,M26_TDI_INV,M26_TMS_INV,M26_TCK,M26_RESETB})
);

wire CMD_DATA, CMD_CLK;

wire TRIGGER_ENABLE; // from CMD FSM
wire CMD_READY; // from CMD FSM
wire CMD_START_FLAG;
wire TRIGGER_ACCEPTED_FLAG;
wire CMD_EXT_START_FLAG;
assign CMD_EXT_START_FLAG = TRIGGER_ACCEPTED_FLAG;
wire EXT_TRIGGER_ENABLE;

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

    .CMD_CLK_IN(CLK40),
    .CMD_CLK_OUT(CMD_CLK),
    .CMD_DATA(CMD_DATA),
    
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(EXT_TRIGGER_ENABLE),
    .CMD_READY(CMD_READY),
    .CMD_START_FLAG(CMD_START_FLAG)
);
    
OBUFDS #(
  .IOSTANDARD("LVDS_25"),
  .SLEW("SLOW") 
) OBUFDS_inst_cmd_clk_out (
  .O(CMD_CLK_P),
  .OB(CMD_CLK_N), 
  .I(CMD_CLK)    
);

OBUFDS #(
  .IOSTANDARD("LVDS_25"), 
  .SLEW("SLOW")
) OBUFDS_inst_cmd_data (
  .O(CMD_DATA_P), 
  .OB(CMD_DATA_N), 
  .I(CMD_DATA) 
);


wire TRIGGER_ACKNOWLEDGE_FLAG; // to TLU FSM
reg CMD_READY_FF;
always @ (posedge CLK40)
begin
    CMD_READY_FF <= CMD_READY;
end
assign TRIGGER_ACKNOWLEDGE_FLAG = CMD_READY & ~CMD_READY_FF;


wire TRIGGER_FIFO_READ;
wire TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA;
wire TRIGGER_FIFO_PEEMPT_REQ;
wire [31:0] TIMESTAMP;
wire TDC_OUT;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
    .ABUSWIDTH(32)
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
    
    .TRIGGER({7'b0, TDC_OUT}),
    .TRIGGER_VETO({7'b0, FIFO_FULL}),
    
    .EXT_TRIGGER_ENABLE(EXT_TRIGGER_ENABLE),
    .TRIGGER_ACKNOWLEDGE(EXT_TRIGGER_ENABLE == 1'b0 ? TRIGGER_ACCEPTED_FLAG : TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),
    
    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(RJ45_BUSY_LEMO_TX1),
    .TLU_CLOCK(RJ45_CLK_LEMO_TX0),
    
    .TIMESTAMP(TIMESTAMP)
);

reg [31:0] timestamp_gray;
always@(posedge BUS_CLK) 
    timestamp_gray <=  (TIMESTAMP>>1) ^ TIMESTAMP;

wire DOBOUT;
wire RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL;
wire FE_FIFO_READ;
wire FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA;
    
fei4_rx #(
    .BASEADDR(RX_BASEADDR),
    .HIGHADDR(RX_HIGHADDR),
    .DSIZE(10),
    .DATA_IDENTIFIER(1),
    .ABUSWIDTH(32)
) i_fei4_rx (
    .RX_CLK(CLK160),
    .RX_CLK2X(CLK320),
    .DATA_CLK(CLK16),

    .RX_DATA(DOBOUT),

    .RX_READY(RX_READY),
    .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR),
    .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR),

    .FIFO_READ(FE_FIFO_READ),
    .FIFO_EMPTY(FE_FIFO_EMPTY),
    .FIFO_DATA(FE_FIFO_DATA),

    .RX_FIFO_FULL(RX_FIFO_FULL),

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
    .I(DOBOUT_P),  
    .IB(DOBOUT_N)
);


wire [5:0] M26_CLK;
wire [5:0] M26_CLK_BUFG;
wire [5:0] M26_MKD;
wire [5:0] M26_DATA0;
wire [5:0] M26_DATA0_RX;
wire [5:0] M26_DATA1;
wire [5:0] M26_DATA1_RX;

assign M26_DATA0 = ~M26_DATA0_RX;
assign M26_DATA1 = M26_DATA1_RX;

wire [5:0] LOST_ERROR;
wire [5:0] FIFO_READ_M26_RX;
wire [5:0] FIFO_EMPTY_M26_RX;
wire [31:0] FIFO_DATA_M26_RX [5:0];
     
genvar ch;
generate
    for (ch = 0; ch < 6; ch = ch + 1) begin: m26_gen

        IBUFDS #(
            .DIFF_TERM("TRUE"), 
            .IBUF_LOW_PWR("FALSE"), 
            .IOSTANDARD("LVDS_25") 
        ) IBUFDS_inst_M26_CLK(
            .O(M26_CLK[ch]), 
            .I(M26_CLK_P[ch]),  
            .IB(M26_CLK_N[ch])
        );
             
        IBUFDS #(
            .DIFF_TERM("TRUE"), 
            .IBUF_LOW_PWR("FALSE"), 
            .IOSTANDARD("LVDS_25") 
        ) IBUFDS_inst_M26_MKD(
            .O(M26_MKD[ch]), 
            .I(M26_MKD_P[ch]),  
            .IB(M26_MKD_N[ch])
        );

        IBUFDS #(
            .DIFF_TERM("TRUE"), 
            .IBUF_LOW_PWR("FALSE"), 
            .IOSTANDARD("LVDS_25") 
        ) IBUFDS_inst_M26_DATA0(
            .O(M26_DATA0_RX[ch]), 
            .I(M26_DATA0_P[ch]),  
            .IB(M26_DATA0_N[ch])
        );
        
        IBUFDS #(
            .DIFF_TERM("TRUE"), 
            .IBUF_LOW_PWR("FALSE"), 
            .IOSTANDARD("LVDS_25") 
        ) IBUFDS_inst_M26_DATA1(
            .O(M26_DATA1_RX[ch]),
            .I(M26_DATA1_P[ch]),  
            .IB(M26_DATA1_N[ch])
        );   


       
end   
endgenerate     

assign FIFO_EMPTY_M26_RX = 6'hff;


wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
wire [31:0] TIMESTAMP;
wire LEMO_TRIGGER_FROM_TDC;
wire TDC_IN_FROM_TDC;
wire RJ45_HITOR;

IBUFDS #(
    .DIFF_TERM("TRUE"), 
    .IBUF_LOW_PWR("FALSE"), 
    .IOSTANDARD("LVDS_25") 
) IBUFDS_inst_RJ45_HITOR (
    .O(RJ45_HITOR), 
    .I(RJ45_HITOR_P),  
    .IB(RJ45_HITOR_N)
);

 
tdc_s3 #(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .ABUSWIDTH(32),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100), // one-hot
    .FAST_TDC(1),
    .FAST_TRIGGER(0)
) i_tdc (
    .CLK320(CLK320),
    .CLK160(CLK160),
    .DV_CLK(CLK40),
    .TDC_IN(RJ45_HITOR),
    .TDC_OUT(TDC_OUT),
    .TRIG_IN(),
    .TRIG_OUT(),

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

wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [8:0] READ_GRANT;

rrp_arbiter #(
    .WIDTH(9)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TDC_FIFO_EMPTY, ~FIFO_EMPTY_M26_RX, ~FE_FIFO_EMPTY, ~TRIGGER_FIFO_EMPTY}),
    .HOLD_REQ({8'b0, TRIGGER_FIFO_PEEMPT_REQ }),
    .DATA_IN({TDC_FIFO_DATA, FIFO_DATA_M26_RX[5], FIFO_DATA_M26_RX[4], FIFO_DATA_M26_RX[3], FIFO_DATA_M26_RX[2], FIFO_DATA_M26_RX[1], FIFO_DATA_M26_RX[0], FE_FIFO_DATA, TRIGGER_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TRIGGER_FIFO_READ = READ_GRANT[0];
assign FE_FIFO_READ = READ_GRANT[1];
assign FIFO_READ_M26_RX = READ_GRANT[7:2];
assign TDC_FIFO_READ = READ_GRANT[8];

//cdc_fifo is for timing reasons
wire [31:0] cdc_data_out;
wire full_32to8, cdc_fifo_empty;
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

wire FIFO_EMPTY, FIFO_FULL;
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

assign LED[7:6] = 2'hf;
assign LED[0] = RX_READY;
assign LED[1] = ~(|LOST_ERROR & CLK_1HZ);
assign LED[2] = ~(|RX_8B10B_DECODER_ERR & CLK_1HZ);

//ila_0 ila(
//    .clk(CLK320),
//    .probe0({M26_DATA1, M26_DATA0, M26_MKD, M26_CLK})
//);

endmodule
