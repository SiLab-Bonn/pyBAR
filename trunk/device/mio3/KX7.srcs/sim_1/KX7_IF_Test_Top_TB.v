`timescale 1ps / 100fs

////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer:
//
// Create Date:   14:30:52 01/22/2014
// Design Name:   KX7_IF_Test_Top
// Module Name:   D:/redmine_svn/usb/FX3device/branches/Hans/KX7 firmware/KX7_IF_Test_Top_TB.v
// Project Name:  KX7_IF_Test
// Target Device:  
// Tool versions:  
// Description: 
//
// Verilog Test Fixture created by ISE for module: KX7_IF_Test_Top
//
// Dependencies:
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
////////////////////////////////////////////////////////////////////////////////


module KX7_IF_Test_Top_TB;

   //***************************************************************************
   // The following parameters refer to width of various ports
   //***************************************************************************
//   parameter BANK_WIDTH            = 3;
                                     // # of memory Bank Address bits.
//   parameter CK_WIDTH              = 1;
                                     // # of CK/CK# outputs to memory.
   parameter COL_WIDTH             = 10;
                                     // # of memory Column Address bits.
   parameter CS_WIDTH              = 1;
                                     // # of unique CS outputs to memory.
//   parameter nCS_PER_RANK          = 1;
                                     // # of unique CS outputs per rank for phy
//   parameter CKE_WIDTH             = 1;
                                     // # of CKE outputs to memory.
//   parameter DATA_BUF_ADDR_WIDTH   = 5;
//   parameter DQ_CNT_WIDTH          = 3;
                                     // = ceil(log2(DQ_WIDTH))
//   parameter DQ_PER_DM             = 8;
   parameter DM_WIDTH              = 1;
                                     // # of DM (data mask)
   parameter DQ_WIDTH              = 8;
                                     // # of DQ (data)
   parameter DQS_WIDTH             = 1;
   parameter DQS_CNT_WIDTH         = 1;
                                     // = ceil(log2(DQS_WIDTH))
   parameter DRAM_WIDTH            = 8;
                                     // # of DQ per DQS
   parameter ECC                   = "OFF";
//   parameter nBANK_MACHS           = 4;
   parameter RANKS                 = 1;
                                     // # of Ranks.
   parameter ODT_WIDTH             = 1;
                                     // # of ODT outputs to memory.
   parameter ROW_WIDTH             = 15;
                                     // # of memory Row Address bits.
   parameter ADDR_WIDTH            = 29;
                                     // # = RANK_WIDTH + BANK_WIDTH
                                     //     + ROW_WIDTH + COL_WIDTH;
                                     // Chip Select is always tied to low for
                                     // single rank devices
//   parameter USE_CS_PORT          = 1;
                                     // # = 1, When CS output is enabled
                                     //   = 0, When CS output is disabled
                                     // If CS_N disabled, user must connect
                                     // DRAM CS_N input(s) to ground
//   parameter USE_DM_PORT           = 0;
                                     // # = 1, When Data Mask option is enabled
                                     //   = 0, When Data Mask option is disbaled
                                     // When Data Mask option is disabled in
                                     // MIG Controller Options page, the logic
                                     // related to Data Mask should not get
                                     // synthesized
//   parameter USE_ODT_PORT          = 1;
                                     // # = 1, When ODT output is enabled
                                     //   = 0, When ODT output is disabled
                                     // Parameter configuration for Dynamic ODT support:
                                     // USE_ODT_PORT = 0, RTT_NOM = "DISABLED", RTT_WR = "60/120".
                                     // This configuration allows to save ODT pin mapping from FPGA.
                                     // The user can tie the ODT input of DRAM to HIGH.

   //***************************************************************************
   // The following parameters are mode register settings
   //***************************************************************************
//   parameter AL                    = "0";
                                     // DDR3 SDRAM:
                                     // Additive Latency (Mode Register 1).
                                     // # = "0", "CL-1", "CL-2".
                                     // DDR2 SDRAM:
                                     // Additive Latency (Extended Mode Register).
//   parameter nAL                   = 0;
                                     // # Additive Latency in number of clock
                                     // cycles.
   parameter BURST_MODE            = "8";
                                     // DDR3 SDRAM:
                                     // Burst Length (Mode Register 0).
                                     // # = "8", "4", "OTF".
                                     // DDR2 SDRAM:
                                     // Burst Length (Mode Register).
                                     // # = "8", "4".
//   parameter BURST_TYPE            = "SEQ";
                                     // DDR3 SDRAM: Burst Type (Mode Register 0).
                                     // DDR2 SDRAM: Burst Type (Mode Register).
                                     // # = "SEQ" - (Sequential),
                                     //   = "INT" - (Interleaved).
//   parameter CL                    = 6;
                                     // in number of clock cycles
                                     // DDR3 SDRAM: CAS Latency (Mode Register 0).
                                     // DDR2 SDRAM: CAS Latency (Mode Register).
//   parameter CWL                   = 5;
                                     // in number of clock cycles
                                     // DDR3 SDRAM: CAS Write Latency (Mode Register 2).
                                     // DDR2 SDRAM: Can be ignored
//   parameter OUTPUT_DRV            = "HIGH";
                                     // Output Driver Impedance Control (Mode Register 1).
                                     // # = "HIGH" - RZQ/7,
                                     //   = "LOW" - RZQ/6.
//   parameter RTT_NOM               = "60";
                                     // RTT_NOM (ODT) (Mode Register 1).
                                     // # = "DISABLED" - RTT_NOM disabled,
                                     //   = "120" - RZQ/2,
                                     //   = "60"  - RZQ/4,
                                     //   = "40"  - RZQ/6.
//   parameter RTT_WR                = "OFF";
                                     // RTT_WR (ODT) (Mode Register 2).
                                     // # = "OFF" - Dynamic ODT off,
                                     //   = "120" - RZQ/2,
                                     //   = "60"  - RZQ/4,
//   parameter ADDR_CMD_MODE         = "1T" ;
                                     // # = "1T", "2T".
//   parameter REG_CTRL              = "OFF";
                                     // # = "ON" - RDIMMs,
                                     //   = "OFF" - Components, SODIMMs, UDIMMs.
   parameter CA_MIRROR             = "OFF";
                                     // C/A mirror opt for DDR3 dual rank
   
   //***************************************************************************
   // The following parameters are multiplier and divisor factors for PLLE2.
   // Based on the selected design frequency these parameters vary.
   //***************************************************************************
   parameter CLKIN_PERIOD          = 5000;
                                     // Input Clock Period
//   parameter CLKFBOUT_MULT         = 4;
                                     // write PLL VCO multiplier
//   parameter DIVCLK_DIVIDE         = 1;
                                     // write PLL VCO divisor
//   parameter CLKOUT0_DIVIDE        = 2;
                                     // VCO output divisor for PLL output clock (CLKOUT0)
//   parameter CLKOUT1_DIVIDE        = 2;
                                     // VCO output divisor for PLL output clock (CLKOUT1)
//   parameter CLKOUT2_DIVIDE        = 32;
                                     // VCO output divisor for PLL output clock (CLKOUT2)
//   parameter CLKOUT3_DIVIDE        = 8;
                                     // VCO output divisor for PLL output clock (CLKOUT3)

   //***************************************************************************
   // Memory Timing Parameters. These parameters varies based on the selected
   // memory part.
   //***************************************************************************
//   parameter tCKE                  = 5000;
                                     // memory tCKE paramter in pS
//   parameter tFAW                  = 40000;
                                     // memory tRAW paramter in pS.
//   parameter tRAS                  = 35000;
                                     // memory tRAS paramter in pS.
//   parameter tRCD                  = 13750;
                                     // memory tRCD paramter in pS.
//   parameter tREFI                 = 7800000;
                                     // memory tREFI paramter in pS.
//   parameter tRFC                  = 300000;
                                     // memory tRFC paramter in pS.
//   parameter tRP                   = 13750;
                                     // memory tRP paramter in pS.
//   parameter tRRD                  = 7500;
                                     // memory tRRD paramter in pS.
//   parameter tRTP                  = 7500;
                                     // memory tRTP paramter in pS.
//   parameter tWTR                  = 7500;
                                     // memory tWTR paramter in pS.
//   parameter tZQI                  = 128_000_000;
                                     // memory tZQI paramter in nS.
//   parameter tZQCS                 = 64;
                                     // memory tZQCS paramter in clock cycles.

   //***************************************************************************
   // Simulation parameters
   //***************************************************************************
   parameter SIM_BYPASS_INIT_CAL   = "FAST";
                                     // # = "SIM_INIT_CAL_FULL" -  Complete
                                     //              memory init &
                                     //              calibration sequence
                                     // # = "SKIP" - Not supported
                                     // # = "FAST" - Complete memory init & use
                                     //              abbreviated calib sequence

   //***************************************************************************
   // The following parameters varies based on the pin out entered in MIG GUI.
   // Do not change any of these parameters directly by editing the RTL.
   // Any changes required should be done through GUI and the design regenerated.
   //***************************************************************************
//   parameter BYTE_LANES_B0         = 4'b1111;
                                     // Byte lanes used in an IO column.
//   parameter BYTE_LANES_B1         = 4'b0000;
                                     // Byte lanes used in an IO column.
//   parameter BYTE_LANES_B2         = 4'b0000;
                                     // Byte lanes used in an IO column.
//   parameter BYTE_LANES_B3         = 4'b0000;
                                     // Byte lanes used in an IO column.
//   parameter BYTE_LANES_B4         = 4'b0000;
                                     // Byte lanes used in an IO column.
//   parameter DATA_CTL_B0           = 4'b0001;
                                     // Indicates Byte lane is data byte lane
                                     // or control Byte lane. '1' in a bit
                                     // position indicates a data byte lane and
                                     // a '0' indicates a control byte lane
//   parameter DATA_CTL_B1           = 4'b0000;
                                     // Indicates Byte lane is data byte lane
                                     // or control Byte lane. '1' in a bit
                                     // position indicates a data byte lane and
                                     // a '0' indicates a control byte lane
//   parameter DATA_CTL_B2           = 4'b0000;
                                     // Indicates Byte lane is data byte lane
                                     // or control Byte lane. '1' in a bit
                                     // position indicates a data byte lane and
                                     // a '0' indicates a control byte lane
//   parameter DATA_CTL_B3           = 4'b0000;
                                     // Indicates Byte lane is data byte lane
                                     // or control Byte lane. '1' in a bit
                                     // position indicates a data byte lane and
                                     // a '0' indicates a control byte lane
//   parameter DATA_CTL_B4           = 4'b0000;
                                     // Indicates Byte lane is data byte lane
                                     // or control Byte lane. '1' in a bit
                                     // position indicates a data byte lane and
                                     // a '0' indicates a control byte lane
//   parameter PHY_0_BITLANES        = 48'h43E_FF8_C7F_0FF;
//   parameter PHY_1_BITLANES        = 48'h000_000_000_000;
//   parameter PHY_2_BITLANES        = 48'h000_000_000_000;

   // control/address/data pin mapping parameters
//   parameter CK_BYTE_MAP
//     = 144'h00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_01;
//   parameter ADDR_MAP
//     = 192'h000_023_024_025_02A_02B_026_027_028_029_031_032_033_034_035_03A;
//   parameter BANK_MAP   = 36'h015_01A_01B;
//   parameter CAS_MAP    = 12'h013;
//   parameter CKE_ODT_BYTE_MAP = 8'h00;
//   parameter CKE_MAP    = 96'h000_000_000_000_000_000_000_010;
//   parameter ODT_MAP    = 96'h000_000_000_000_000_000_000_011;
//   parameter CS_MAP     = 120'h000_000_000_000_000_000_000_000_000_016;
//   parameter PARITY_MAP = 12'h000;
//   parameter RAS_MAP    = 12'h014;
//   parameter WE_MAP     = 12'h012;
//   parameter DQS_BYTE_MAP
//     = 144'h00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_00_00;
//   parameter DATA0_MAP  = 96'h000_001_002_003_004_005_006_007;
//   parameter DATA1_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA2_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA3_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA4_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA5_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA6_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA7_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA8_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA9_MAP  = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA10_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA11_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA12_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA13_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA14_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA15_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA16_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter DATA17_MAP = 96'h000_000_000_000_000_000_000_000;
//   parameter MASK0_MAP  = 108'h000_000_000_000_000_000_000_000_000;
//   parameter MASK1_MAP  = 108'h000_000_000_000_000_000_000_000_000;

//   parameter SLOT_0_CONFIG         = 8'b0000_0001;
                                     // Mapping of Ranks.
//   parameter SLOT_1_CONFIG         = 8'b0000_0000;
                                     // Mapping of Ranks.
//   parameter MEM_ADDR_ORDER        = "BANK_ROW_COLUMN";
                                      //Possible Parameters
                                      //1.BANK_ROW_COLUMN : Address mapping is
                                      //                    in form of Bank Row Column.
                                      //2.ROW_BANK_COLUMN : Address mapping is
                                      //                    in the form of Row Bank Column.
                                      //3.TG_TEST : Scrambles Address bits
                                      //            for distributed Addressing.
   //***************************************************************************
   // IODELAY and PHY related parameters
   //***************************************************************************
//   parameter IBUF_LPWR_MODE        = "OFF";
                                     // to phy_top
//   parameter DATA_IO_IDLE_PWRDWN   = "ON";
                                     // # = "ON", "OFF"
//   parameter DATA_IO_PRIM_TYPE     = "HP_LP";
                                     // # = "HP_LP", "HR_LP", "DEFAULT"
//   parameter USER_REFRESH          = "OFF";
//   parameter WRLVL                 = "ON";
                                     // # = "ON" - DDR3 SDRAM
                                     //   = "OFF" - DDR2 SDRAM.
//   parameter ORDERING              = "NORM";
                                     // # = "NORM", "STRICT", "RELAXED".
//   parameter CALIB_ROW_ADD         = 16'h0000;
                                     // Calibration row address will be used for
                                     // calibration read and write operations
//   parameter CALIB_COL_ADD         = 12'h000;
                                     // Calibration column address will be used for
                                     // calibration read and write operations
//   parameter CALIB_BA_ADD          = 3'h0;
                                     // Calibration bank address will be used for
                                     // calibration read and write operations
   parameter TCQ                   = 100;
   //***************************************************************************
   // IODELAY and PHY related parameters
   //***************************************************************************
//   parameter IODELAY_GRP           = "DDR_A_IODELAY_MIG";
                                     // It is associated to a set of IODELAYs with
                                     // an IDELAYCTRL that have same IODELAY CONTROLLER
                                     // clock frequency.
//   parameter SYSCLK_TYPE           = "DIFFERENTIAL";
                                     // System clock type DIFFERENTIAL, SINGLE_ENDED,
                                     // NO_BUFFER
//   parameter REFCLK_TYPE           = "USE_SYSTEM_CLOCK";
                                     // Reference clock type DIFFERENTIAL, SINGLE_ENDED,
                                     // NO_BUFFER, USE_SYSTEM_CLOCK
   parameter RST_ACT_LOW           = 1;
                                     // =1 for active low reset,
                                     // =0 for active high.
//   parameter CAL_WIDTH             = "HALF";
//   parameter STARVE_LIMIT          = 2;
                                     // # = 2,3,4.

   //***************************************************************************
   // Referece clock frequency parameters
   //***************************************************************************
   parameter REFCLK_FREQ           = 200.0;
                                     // IODELAYCTRL reference clock frequency
   //***************************************************************************
   // System clock frequency parameters
   //***************************************************************************
   parameter tCK                   = 2500;
                                     // memory tCK paramter.
                     // # = Clock Period in pS.
   parameter nCK_PER_CLK           = 4;
                                     // # of memory CKs per fabric CLK

   

   //***************************************************************************
   // Debug and Internal parameters
   //***************************************************************************
   parameter DEBUG_PORT            = "OFF";
                                     // # = "ON" Enable debug signals/controls.
                                     //   = "OFF" Disable debug signals/controls.
   //***************************************************************************
   // Debug and Internal parameters
   //***************************************************************************
   parameter DRAM_TYPE             = "DDR3";

    

  //**************************************************************************//
  // Local parameters Declarations
  //**************************************************************************//

  localparam real TPROP_DQS          = 0.00;
                                       // Delay for DQS signal during Write Operation
  localparam real TPROP_DQS_RD       = 0.00;
                       // Delay for DQS signal during Read Operation
  localparam real TPROP_PCB_CTRL     = 0.00;
                       // Delay for Address and Ctrl signals
  localparam real TPROP_PCB_DATA     = 0.00;
                       // Delay for data signal during Write operation
  localparam real TPROP_PCB_DATA_RD  = 0.00;
                       // Delay for data signal during Read operation

  localparam MEMORY_WIDTH            = 16;
  localparam NUM_COMP                = DQ_WIDTH/MEMORY_WIDTH;
  localparam ECC_TEST 		   	= "OFF" ;
  localparam ERR_INSERT = (ECC_TEST == "ON") ? "OFF" : ECC ;
  

  localparam real REFCLK_PERIOD = (1000000.0/(2*REFCLK_FREQ));
  localparam RESET_PERIOD = 200000; //in pSec  
  localparam real SYSCLK_PERIOD = tCK;

 // from app ui  
  //localparam PAYLOAD_WIDTH         = (ECC_TEST == "OFF") ? DATA_WIDTH : DQ_WIDTH;
  localparam PAYLOAD_WIDTH         = DQ_WIDTH;
  localparam APP_DATA_WIDTH        = 2 * nCK_PER_CLK * PAYLOAD_WIDTH;
  localparam APP_MASK_WIDTH        = APP_DATA_WIDTH / 8;  

  // FX3 SM 
  reg  [31:0] sm_wr_data[255:0];
  reg  [31:0]  sm_addr;
  reg  [31:0]  sm_count;  // value of request counter
  wire  [31:0] sm_rd_data[255:0];
  reg  [31:0]   sm_data_size;
  reg  read_write_n;
  wire [31:0] data_counter;
  reg  trg;
  wire idle;
  reg  [31:0] word_read[255:0];
  reg [31:0] count;
  reg [31:0] data_correct_flag;

	// Outputs
	wire fx3_ack;
	wire fx3_rdy;
	wire [8:1] led;
	wire fx3_pclk_100MHz;
	

	// Bidirs
	wire [31:0] fx3_bus;
	
	
// clock and reset	
	reg  sys_rst_n;
	wire sys_rst;
	reg  sys_clk_i;
	wire sys_clk_p;
	wire sys_clk_n;
	reg  clk_ref_i;
	
	
	
// DDR3 memory

  wire                               ddr3_reset_n;
  wire [DQ_WIDTH-1:0]                ddr3_dq_fpga;
  wire [DQS_WIDTH-1:0]               ddr3_dqs_p_fpga;
  wire [DQS_WIDTH-1:0]               ddr3_dqs_n_fpga;
  wire [ROW_WIDTH-1:0]               ddr3_addr_fpga;
  wire [3-1:0]                       ddr3_ba_fpga;
  wire                               ddr3_ras_n_fpga;
  wire                               ddr3_cas_n_fpga;
  wire                               ddr3_we_n_fpga;
  wire [1-1:0]                       ddr3_cke_fpga;
  wire [1-1:0]                       ddr3_ck_p_fpga;
  wire [1-1:0]                       ddr3_ck_n_fpga;
    
  
  wire                               init_calib_complete;
  wire                               tg_compare_error;
  wire [(CS_WIDTH*1)-1:0]            ddr3_cs_n_fpga;	
  
  wire [ODT_WIDTH-1:0]               ddr3_odt_fpga;
    
  
  reg [(CS_WIDTH*1)-1:0]             ddr3_cs_n_sdram_tmp;
    
  
  reg [ODT_WIDTH-1:0]                ddr3_odt_sdram_tmp;
    

  
  wire [DQ_WIDTH-1:0]                ddr3_dq_sdram;
  reg [ROW_WIDTH-1:0]                ddr3_addr_sdram [0:1];
  reg [3-1:0]                        ddr3_ba_sdram [0:1];
  reg                                ddr3_ras_n_sdram;
  reg                                ddr3_cas_n_sdram;
  reg                                ddr3_we_n_sdram;
  wire [(CS_WIDTH*1)-1:0]            ddr3_cs_n_sdram;
  wire [ODT_WIDTH-1:0]               ddr3_odt_sdram;
  reg [1-1:0]                        ddr3_cke_sdram;
  wire [DM_WIDTH-1:0]                ddr3_dm_sdram;
  wire [DQS_WIDTH-1:0]               ddr3_dqs_p_sdram;
  wire [DQS_WIDTH-1:0]               ddr3_dqs_n_sdram;
  reg [1-1:0]                        ddr3_ck_p_sdram;
  reg [1-1:0]                        ddr3_ck_n_sdram;
  
  
  
  always @( * ) begin
    ddr3_ck_p_sdram      <=  #(TPROP_PCB_CTRL) ddr3_ck_p_fpga;
    ddr3_ck_n_sdram      <=  #(TPROP_PCB_CTRL) ddr3_ck_n_fpga;
    ddr3_addr_sdram[0]   <=  #(TPROP_PCB_CTRL) ddr3_addr_fpga;
    ddr3_addr_sdram[1]   <=  #(TPROP_PCB_CTRL) (CA_MIRROR == "ON") ?
                                                 {ddr3_addr_fpga[ROW_WIDTH-1:9],
                                                  ddr3_addr_fpga[7], ddr3_addr_fpga[8],
                                                  ddr3_addr_fpga[5], ddr3_addr_fpga[6],
                                                  ddr3_addr_fpga[3], ddr3_addr_fpga[4],
                                                  ddr3_addr_fpga[2:0]} :
                                                 ddr3_addr_fpga;
    ddr3_ba_sdram[0]     <=  #(TPROP_PCB_CTRL) ddr3_ba_fpga;
    ddr3_ba_sdram[1]     <=  #(TPROP_PCB_CTRL) (CA_MIRROR == "ON") ?
                                                 {ddr3_ba_fpga[3-1:2],
                                                  ddr3_ba_fpga[0],
                                                  ddr3_ba_fpga[1]} :
                                                 ddr3_ba_fpga;
    ddr3_ras_n_sdram     <=  #(TPROP_PCB_CTRL) ddr3_ras_n_fpga;
    ddr3_cas_n_sdram     <=  #(TPROP_PCB_CTRL) ddr3_cas_n_fpga;
    ddr3_we_n_sdram      <=  #(TPROP_PCB_CTRL) ddr3_we_n_fpga;
    ddr3_cke_sdram       <=  #(TPROP_PCB_CTRL) ddr3_cke_fpga;
  end
    

  always @( * )
    ddr3_cs_n_sdram_tmp   <=  #(TPROP_PCB_CTRL) ddr3_cs_n_fpga;
  assign ddr3_cs_n_sdram =  ddr3_cs_n_sdram_tmp;
    

  assign ddr3_dm_sdram =  {DM_WIDTH{1'b0}};//DM signal generation
    

  always @( * )
    ddr3_odt_sdram_tmp  <=  #(TPROP_PCB_CTRL) ddr3_odt_fpga;
  assign ddr3_odt_sdram =  ddr3_odt_sdram_tmp;
    

// Controlling the bi-directional BUS

  genvar dqwd;
  generate
    for (dqwd = 1;dqwd < DQ_WIDTH;dqwd = dqwd+1) begin : dq_delay
      WireDelay #
       (
        .Delay_g    (TPROP_PCB_DATA),
        .Delay_rd   (TPROP_PCB_DATA_RD),
        .ERR_INSERT ("OFF")
       )
      u_delay_dq
       (
        .A             (ddr3_dq_fpga[dqwd]),
        .B             (ddr3_dq_sdram[dqwd]),
        .reset         (sys_rst_n),
        .phy_init_done (init_calib_complete)
       );
    end
    // For ECC ON case error is inserted on LSB bit from DRAM to FPGA
          WireDelay #
       (
        .Delay_g    (TPROP_PCB_DATA),
        .Delay_rd   (TPROP_PCB_DATA_RD),
        .ERR_INSERT (ERR_INSERT)
       )
      u_delay_dq_0
       (
        .A             (ddr3_dq_fpga[0]),
        .B             (ddr3_dq_sdram[0]),
        .reset         (sys_rst_n),
        .phy_init_done (init_calib_complete)
       );
  endgenerate

  genvar dqswd;
  generate
    for (dqswd = 0;dqswd < DQS_WIDTH;dqswd = dqswd+1) begin : dqs_delay
      WireDelay #
       (
        .Delay_g    (TPROP_DQS),
        .Delay_rd   (TPROP_DQS_RD),
        .ERR_INSERT ("OFF")
       )
      u_delay_dqs_p
       (
        .A             (ddr3_dqs_p_fpga[dqswd]),
        .B             (ddr3_dqs_p_sdram[dqswd]),
        .reset         (sys_rst_n),
        .phy_init_done (init_calib_complete)
       );

      WireDelay #
       (
        .Delay_g    (TPROP_DQS),
        .Delay_rd   (TPROP_DQS_RD),
        .ERR_INSERT ("OFF")
       )
      u_delay_dqs_n
       (
        .A             (ddr3_dqs_n_fpga[dqswd]),
        .B             (ddr3_dqs_n_sdram[dqswd]),
        .reset         (sys_rst_n),
        .phy_init_done (init_calib_complete)
       );
    end
  endgenerate
 
FX3_GPIF_SM FX3_GPIF_SM_inst(
      .count(sm_count),
      .addr(sm_addr),
      .wr_data(sm_wr_data[data_counter]),
      .data_size(sm_data_size),
      .read_write_n(read_write_n),
      .data_counter(data_counter),
      .rd_data(sm_rd_data[0]),
      .trg(trg),
      .idle(idle),
      .clk(fx3_pclk_100MHz),
      .rst(!sys_rst_n),
//      .fx3_aden(fx3_aden),
//      .fx3_rd(fx3_rd),
//      .fx3_counten(fx3_counten),
      .fx3_wr(fx3_wr),
      .fx3_oe(fx3_oe),
      .fx3_cs(fx3_cs),
      .fx3_rst(fx3_rst),
      .fx3_rdy(fx3_rdy),
      .fx3_valid(fx3_ack),
      .fx3_bus(fx3_bus)
      );    
  

	// Instantiate the Unit Under Test (UUT)
	KX7_IF_Test_Top uut (
		.fx3_pclk_100MHz(fx3_pclk_100MHz), 
//		.fx3_rd(fx3_rd), 
//		.fx3_counten(fx3_counten), 
		.fx3_wr(fx3_wr), 
		.fx3_cs(fx3_cs), 
		.fx3_oe(fx3_oe), 
//		.fx3_aden(fx3_aden), 
		.fx3_rst(fx3_rst), 
		.fx3_ack(fx3_ack), 
		.fx3_rdy(fx3_rdy), 
		.fx3_bus(fx3_bus), 
		.led(led),
		
    // DDR3 interface (256Mb x 8)
     .ddr3_dq(ddr3_dq_fpga),
     .ddr3_addr(ddr3_addr_fpga),
     .ddr3_dqs_p(ddr3_dqs_p_fpga),
     .ddr3_dqs_n(ddr3_dqs_n_fpga),
     .ddr3_ba(ddr3_ba_fpga),
     .ddr3_ck_p(ddr3_ck_p_fpga),
     .ddr3_ck_n(ddr3_ck_n_fpga),
     .ddr3_ras_n(ddr3_ras_n_fpga),
     .ddr3_cas_n(ddr3_cas_n_fpga),
     .ddr3_we_n(ddr3_we_n_fpga),
     .ddr3_reset_n(ddr3_reset_n),
     .ddr3_cke(ddr3_cke_fpga),
     .ddr3_odt(ddr3_odt_fpga),
     .ddr3_cs_n(ddr3_cs_n_fpga),
    
    // 200 MHz oscillator
     .sys_clk_p(sys_clk_p), 
     .sys_clk_n(sys_clk_n),
     
     .INIT_COMPLETE(init_calib_complete)
 		
	);

  
  
  
   //**************************************************************************//
  // Reset Generation
  //**************************************************************************//
  initial begin
    sys_rst_n = 1'b0;
    #RESET_PERIOD
      sys_rst_n = 1'b1;
   end

   assign sys_rst = RST_ACT_LOW ? sys_rst_n : ~sys_rst_n;

  //**************************************************************************//
  // Clock Generation
  //**************************************************************************//

  initial
    sys_clk_i = 1'b0;
  always
    sys_clk_i = #(CLKIN_PERIOD/2.0) ~sys_clk_i;

  assign sys_clk_p = sys_clk_i;
  assign sys_clk_n = ~sys_clk_i;

  initial
    clk_ref_i = 1'b0;
  always
    clk_ref_i = #REFCLK_PERIOD ~clk_ref_i;
    
  always @(posedge fx3_pclk_100MHz)
    word_read[(data_counter-1)] = sm_rd_data[0];

	initial 
	begin
		// Initialize Inputs
    sm_addr      = 0;
    sm_count     = 0;
    sm_data_size = 0;
    read_write_n = 0;
    trg = 1'b0;	
    count = 0;
    data_correct_flag = 0;
	end


	initial
	begin 
  wait  (ddr3_reset_n & init_calib_complete)
  begin
    repeat (551) @(posedge fx3_pclk_100MHz);
    
   /* @(posedge fx3_pclk_100MHz);
    sys_rst_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    sys_rst_n = 1'b1;
    repeat (50) @(posedge fx3_pclk_100MHz);*/

// Writing to DDR
    
    sm_addr       = 32'h21_00_00_00;	
    repeat (1) begin
       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
       count = count + 1;
    end
  	   /*sm_wr_data[0] = 32'h68_75_28_36;
  	   sm_wr_data[1] = 32'h08_07_06_05;*/
    sm_data_size = 1;
    read_write_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (511) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
 
// End of writing to DDR
     
    /*sm_addr       = 32'h20_00_00_00;	
    repeat (256) begin
       sm_wr_data[count] = *//*count*//*({$random} % (32'hFF_FF_FF_FF));
       count = count + 1;
    end
       *//*sm_wr_data[0] = 32'h68_75_28_36;
       sm_wr_data[1] = 32'h08_07_06_05;*//*
    sm_data_size = 256;
    read_write_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (500) @(posedge fx3_pclk_100MHz);*/
    
// Reading form DDR
    
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h00_00_00_00;
    repeat (10) @(posedge fx3_pclk_100MHz);
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h21_00_00_00;
    sm_count      = 1;
    read_write_n = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (486) @(posedge fx3_pclk_100MHz);
    
// End of reading from DDR

// Data integrity check
    
    repeat (1) begin
       if (sm_wr_data[count] == word_read[count])
          data_correct_flag = 0;
       else
          data_correct_flag = count;
       count = count + 1;
    end
    
    repeat (95) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
    
// End of data integrity check

// Writing to DDR
    
    sm_addr       = 32'h20_00_01_00;	
    repeat (256) begin
       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
      count = count + 1;
    end
 	   /*sm_wr_data[0] = 32'h68_75_28_36;
  	   sm_wr_data[1] = 32'h08_07_06_05;*/
    sm_data_size = 256;
    read_write_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (506) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
 
// End of writing to DDR

// Reading form DDR
    
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h00_00_00_00;
    repeat (10) @(posedge fx3_pclk_100MHz);
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h20_00_01_00;
    sm_count      = 256;
    read_write_n = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (475) @(posedge fx3_pclk_100MHz);
    
// End of reading from DDR

// Data integrity check
    
    repeat (256) begin
       if (sm_wr_data[count] == word_read[count])
          data_correct_flag = 0;
       else
          data_correct_flag = count;
       count = count + 1;
    end
    
    repeat (104) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
    
// End of data integrity check

//// Writing to DDR
    
//    sm_addr       = 32'h20_00_00_00;	
//    repeat (1) begin
//       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
//       count = count + 1;
//    end
//  	   /*sm_wr_data[0] = 32'h68_75_28_36;
//  	   sm_wr_data[1] = 32'h08_07_06_05;*/
//    sm_data_size = 1;
//    read_write_n = 1'b0;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (531) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
 
//// End of writing to DDR

//// Reading form DDR
    
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h00_00_00_00;
//    repeat (10) @(posedge fx3_pclk_100MHz);
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h20_00_00_00;
//    sm_count      = 1;
//    read_write_n = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (540) @(posedge fx3_pclk_100MHz);
    
//// End of reading from DDR

//// Data integrity check
    
//    repeat (1) begin
//       if (sm_wr_data[count] == word_read[count])
//          data_correct_flag = 0;
//       else
//          data_correct_flag = count;
//       count = count + 1;
//    end
    
//    repeat (90) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
    
//// End of data integrity check

//// Writing to DDR
    
//    sm_addr       = 32'h20_00_00_00;	
//    repeat (256) begin
//       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
//       count = count + 1;
//    end
//  	   /*sm_wr_data[0] = 32'h68_75_28_36;
//  	   sm_wr_data[1] = 32'h08_07_06_05;*/
//    sm_data_size = 256;
//    read_write_n = 1'b0;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (489) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
 
//// End of writing to DDR

//// Reading form DDR
    
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h00_00_00_00;
//    repeat (10) @(posedge fx3_pclk_100MHz);
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h20_00_00_00;
//    sm_count      = 256;
//    read_write_n = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (505) @(posedge fx3_pclk_100MHz);
    
//// End of reading from DDR

//// Data integrity check
    
//    repeat (256) begin
//       if (sm_wr_data[count] == word_read[count])
//          data_correct_flag = 0;
//       else
//          data_correct_flag = count;
//       count = count + 1;
//    end
    
//    repeat (100) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
    
//// End of data integrity check

//// Writing to DDR
    
//    sm_addr       = 32'h20_00_00_00;	
//    repeat (256) begin
//       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
//       count = count + 1;
//    end
//  	   /*sm_wr_data[0] = 32'h68_75_28_36;
//  	   sm_wr_data[1] = 32'h08_07_06_05;*/
//    sm_data_size = 256;
//    read_write_n = 1'b0;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (531) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
 
//// End of writing to DDR

//// Reading form DDR
    
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h00_00_00_00;
//    repeat (10) @(posedge fx3_pclk_100MHz);
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h20_00_00_00;
//    sm_count      = 256;
//    read_write_n = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (540) @(posedge fx3_pclk_100MHz);
    
//// End of reading from DDR

//// Data integrity check
    
//    repeat (256) begin
//       if (sm_wr_data[count] == word_read[count])
//          data_correct_flag = 0;
//       else
//          data_correct_flag = count;
//       count = count + 1;
//    end
    
//    repeat (90) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
    
//// End of data integrity check

//// Writing to DDR
    
//    sm_addr       = 32'h20_00_00_00;	
//    repeat (256) begin
//       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
//       count = count + 1;
//    end
//  	   /*sm_wr_data[0] = 32'h68_75_28_36;
//  	   sm_wr_data[1] = 32'h08_07_06_05;*/
//    sm_data_size = 256;
//    read_write_n = 1'b0;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (531) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
 
//// End of writing to DDR

//// Reading form DDR
    
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h00_00_00_00;
//    repeat (10) @(posedge fx3_pclk_100MHz);
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h20_00_00_00;
//    sm_count      = 256;
//    read_write_n = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (540) @(posedge fx3_pclk_100MHz);
    
//// End of reading from DDR

//// Data integrity check
    
//    repeat (256) begin
//       if (sm_wr_data[count] == word_read[count])
//          data_correct_flag = 0;
//       else
//          data_correct_flag = count;
//       count = count + 1;
//    end
    
//    repeat (90) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
    
//// End of data integrity check

//// Writing to DDR
    
//    sm_addr       = 32'h20_00_00_00;	
//    repeat (256) begin
//       sm_wr_data[count] = /*count*/({$random} % (32'hFF_FF_FF_FF));
//       count = count + 1;
//    end
//  	   /*sm_wr_data[0] = 32'h68_75_28_36;
//  	   sm_wr_data[1] = 32'h08_07_06_05;*/
//    sm_data_size = 256;
//    read_write_n = 1'b0;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (531) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
 
//// End of writing to DDR

//// Reading form DDR
    
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h00_00_00_00;
//    repeat (10) @(posedge fx3_pclk_100MHz);
//    @(posedge fx3_pclk_100MHz);
//    sm_addr       = 32'h20_00_00_00;
//    sm_count      = 256;
//    read_write_n = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b1;
//    @(posedge fx3_pclk_100MHz);
//    trg = 1'b0;
    
//    repeat (540) @(posedge fx3_pclk_100MHz);
    
//// End of reading from DDR

//// Data integrity check
    
//    repeat (256) begin
//       if (sm_wr_data[count] == word_read[count])
//          data_correct_flag = 0;
//       else
//          data_correct_flag = count;
//       count = count + 1;
//    end
    
//    repeat (90) @(posedge fx3_pclk_100MHz);
    
//    @(posedge fx3_pclk_100MHz);
//    count = 1'b0;
//    @(posedge fx3_pclk_100MHz);
    
//// End of data integrity check


// Writing to BRAM

    sm_addr       = 32'h10_00_00_00;	
    repeat (256) begin
       sm_wr_data[count] = count/*({$random} % (32'hFF_FF_FF_FF))*/;
       count = count + 1;
    end
  	   /*sm_wr_data[0] = 32'h68_75_28_36;
  	   sm_wr_data[1] = 32'h08_07_06_05;*/
    sm_data_size = 256;
    read_write_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (500) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
    
// End of writing to BRAM

// Reading from BRAM

    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h00_00_00_00;
    repeat (10) @(posedge fx3_pclk_100MHz);
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h10_00_00_00;
    sm_count      = 256;
    read_write_n = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (500) @(posedge fx3_pclk_100MHz);

// End of reading from BRAM

// Data integrity check
    
    repeat (256) begin
       if (sm_wr_data[count] == word_read[count])
          data_correct_flag = 0;
       else
          data_correct_flag = count;
       count = count + 1;
    end
    
    repeat (100) @(posedge fx3_pclk_100MHz);
    
    @(posedge fx3_pclk_100MHz);
    count = 1'b0;
    @(posedge fx3_pclk_100MHz);
    
// End of data integrity check

// Writing to Register

    sm_addr       = 1;	
     
    sm_wr_data[0] = 5;

    sm_data_size = 1;
    read_write_n = 1'b0;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (50) @(posedge fx3_pclk_100MHz);
    
// End of writing to Register

// Reading from Register

    @(posedge fx3_pclk_100MHz);
    sm_addr       = 32'h00_00_00_00;
    repeat (10) @(posedge fx3_pclk_100MHz);
    @(posedge fx3_pclk_100MHz);
    sm_addr       = 1;
    sm_count      = 1;
    read_write_n = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b1;
    @(posedge fx3_pclk_100MHz);
    trg = 1'b0;
    
    repeat (50) @(posedge fx3_pclk_100MHz);

// End of reading from Register

    
	  $finish;
  end  //wait	
	
  end



	
	//**************************************************************************//
  // Memory Models instantiations
  //**************************************************************************//

  genvar r,i;
  generate
    for (r = 0; r < CS_WIDTH; r = r + 1) begin: mem_rnk
      if(DQ_WIDTH/16) begin: mem
        for (i = 0; i < NUM_COMP; i = i + 1) begin: gen_mem
          ddr3_model u_comp_ddr3
            (
             .rst_n   (ddr3_reset_n),
             .ck      (ddr3_ck_p_sdram),
             .ck_n    (ddr3_ck_n_sdram),
             .cke     (ddr3_cke_sdram[r]),
             .cs_n    (ddr3_cs_n_sdram[r]),
             .ras_n   (ddr3_ras_n_sdram),
             .cas_n   (ddr3_cas_n_sdram),
             .we_n    (ddr3_we_n_sdram),
             .dm_tdqs (ddr3_dm_sdram[(2*(i+1)-1):(2*i)]),
             .ba      (ddr3_ba_sdram[r]),
             .addr    (ddr3_addr_sdram[r]),
             .dq      (ddr3_dq_sdram[16*(i+1)-1:16*(i)]),
             .dqs     (ddr3_dqs_p_sdram[(2*(i+1)-1):(2*i)]),
             .dqs_n   (ddr3_dqs_n_sdram[(2*(i+1)-1):(2*i)]),
             .tdqs_n  (),
             .odt     (ddr3_odt_sdram[r])
             );
        end
      end
      if (DQ_WIDTH%16) begin: gen_mem_extrabits
        ddr3_model u_comp_ddr3
          (
           .rst_n   (ddr3_reset_n),
           .ck      (ddr3_ck_p_sdram),
           .ck_n    (ddr3_ck_n_sdram),
           .cke     (ddr3_cke_sdram[r]),
           .cs_n    (ddr3_cs_n_sdram[r]),
           .ras_n   (ddr3_ras_n_sdram),
           .cas_n   (ddr3_cas_n_sdram),
           .we_n    (ddr3_we_n_sdram),
           .dm_tdqs ({ddr3_dm_sdram[DM_WIDTH-1],ddr3_dm_sdram[DM_WIDTH-1]}),
           .ba      (ddr3_ba_sdram[r]),
           .addr    (ddr3_addr_sdram[r]),
           .dq      ({ddr3_dq_sdram[DQ_WIDTH-1:(DQ_WIDTH-8)],
                      ddr3_dq_sdram[DQ_WIDTH-1:(DQ_WIDTH-8)]}),
           .dqs     ({ddr3_dqs_p_sdram[DQS_WIDTH-1],
                      ddr3_dqs_p_sdram[DQS_WIDTH-1]}),
           .dqs_n   ({ddr3_dqs_n_sdram[DQS_WIDTH-1],
                      ddr3_dqs_n_sdram[DQS_WIDTH-1]}),
           .tdqs_n  (),
           .odt     (ddr3_odt_sdram[r])
           );
      end
    end
  endgenerate	
	      
endmodule

