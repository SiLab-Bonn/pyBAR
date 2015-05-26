
module top(

    input wire CLK_50M, // IN
    //SW_RSTn, // IN  // REMOVED THIS SIGNAL BECAUSE NOT IN SEABAS

    output wire [3:0]  REFCLK_P, // OUT
    output wire [3:0]  REFCLK_N, // OUT
    output wire [3:0]  CMDDCI_P, // OUT
    output wire [3:0]  CMDDCI_N, // OUT

    input wire [3:0] DOBOUT_P, // IN
    input wire [3:0] DOBOUT_N, // IN

    output wire [1:0] NIM_OUT, //OUT

    output wire [7:0] LED, // OUT
    // User I/F
    output wire USR_CLK,    // out    : Clock
    input wire  USR_ACTIVE,    // in    : TCP established
    input wire  USR_CLOSE_REQ,    // in    : Request to close a TCP Connection
    output wire USR_CLOSE_ACK,    // out    : Acknowledge for USR_CLOSE_REQ
    // TCP Tx
    input wire  USR_TX_AFULL,    // in    : Almost full flag of a TCP Tx FIFO
    output wire USR_TX_WE,    // out    : TCP Tx Data write enable
    output wire [7:0] USR_TX_WD,    // out    : TCP Tx Data[7:0]
    // TCP Rx
    input wire  USR_RX_EMPTY,    // in    : Empty flag of a TCP RX flag
    output wire USR_RX_RE,    // out    : TCP Rx Data Read enable
    input wire  USR_RX_RV,    // in    : TCP Rx data valid
    input wire  [7:0] USR_RX_RD,    // in    : TCP Rx data[7:0]

    // Register Access
    input wire  REG_CLK,    // in    : Clock
    input wire  REG_ACT,    // in    : Access Active
    output wire REG_DI,    // out    : Serial Data Output
    input wire  REG_DO    // in    : Serial Data Input
    );


//=================================================================
//    Input/Output Buffer for LVDS signal
//=================================================================

wire [3:0] CMD_CLK;
wire [3:0] CMD_DATA;

//----------
// DLL
//----------
wire RST_DLL, SW_RSTn;
assign SW_RSTn = 1'b1;
assign RST_DLL = ~SW_RSTn;

wire CLKIN_IBUFG;

//IBUFG  CLKIN_IBUFG_INST (.I(CLK_50M), .O(CLKIN_IBUFG));
wire CLK0_OUT, CLKFX_BUF, LOCKED1, CLKFB_IN;

(* KEEP = "{TRUE}" *) wire BUS_CLK;
(* KEEP = "{TRUE}" *) wire CLK160;
(* KEEP = "{TRUE}" *) wire CLK320;
(* KEEP = "{TRUE}" *) wire CLK40;
(* KEEP = "{TRUE}" *) wire CLK16;
(* KEEP = "{TRUE}" *) wire CLK125;

//wire CLK125; assign CLK125 = BUS_CLK;

wire LOCKED_OUT;

clock_manager iclock_manager (
    .CLKIN1_IN(CLK_50M), 
    .RST_IN(RST_DLL), 
    .CLKOUT0_OUT(CLK160), 
    .CLKOUT1_OUT(CLK320), 
    .CLKOUT2_OUT(CLK40), 
    .CLKOUT3_OUT(CLK16), 
    .CLKOUT0_OUT2(CLK125),
    .LOCKED_OUT(LOCKED_OUT)
    );              

IBUFG   CLK_REG_BUFG_INST (.I(REG_CLK), .O(BUS_CLK));
//assign BUS_CLK = CLK125;

wire BUS_RST;
assign BUS_RST = !LOCKED_OUT | RST_DLL;


//-------------------------------
//    UDP register Access
//-------------------------------
wire RBCP_WE, RBCP_RE;
wire [7:0] RBCP_WD, RBCP_RD;
wire [31:0] RBCP_ADDR;
wire RBCP_ACK;
    
slave slave(
    .RSTn(~BUS_RST),    // in    : System reset
    .FILL_ADDR(32'h0),    // in    : Filled address for narow address-width
    // Serial I/F
    .SCK(BUS_CLK),    // in    : Clock
    .SCS(REG_ACT),    // in    : Active
    .SI(REG_DI),    // out    : Data input
    .SO(REG_DO),    // in    : Data output
    // Register I/F
    .REG_ADDR(RBCP_ADDR[31:0]),  
    .REG_WD(RBCP_WD[7:0]), 
    .REG_WE(RBCP_WE), 
    .REG_RE(RBCP_RE), 
    .REG_ACK(RBCP_ACK), 
    .REG_RV(RBCP_ACK), 
    .REG_RD(RBCP_RD[7:0])
);

wire BUS_WR, BUS_RD;
wire [31:0] BUS_ADD;
wire [7:0] BUS_DATA;

rbcp_to_bus irbcp_to_bus(

    .BUS_RST(BUS_RST),
    .BUS_CLK(BUS_CLK),

    .RBCP_ACT(1'b1),
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

//-------------------------------
//    Basil modules
//-------------------------------

// -------  MODULE ADREESSES  ------- //
localparam CMD_BASEADDR = 32'h0000;
localparam CMD_HIGHADDR = 32'h1000-1;

localparam FIFO_BASEADDR = 32'h8100;
localparam FIFO_HIGHADDR = 32'h8200-1;

localparam RX4_BASEADDR = 32'h8300;
localparam RX4_HIGHADDR = 32'h8400-1;

localparam RX3_BASEADDR = 32'h8400;
localparam RX3_HIGHADDR = 32'h8500-1;

localparam RX2_BASEADDR = 32'h8500;
localparam RX2_HIGHADDR = 32'h8600-1;

localparam RX1_BASEADDR = 32'h8600;
localparam RX1_HIGHADDR = 32'h8700-1;

localparam GPIO_RX_BASEADDR = 32'h8800;
localparam GPIO_RX_HIGHADDR = 32'h8900-1;

localparam ABUSWIDTH = 32;

cmd_seq 
#( 
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .OUTPUTS(1)
) icmd (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CMD_CLK_OUT(CMD_CLK[0]),
    .CMD_CLK_IN(CLK40),
    
    .CMD_EXT_START_FLAG(1'b0),
    .CMD_EXT_START_ENABLE(),
    .CMD_DATA(CMD_DATA[0]),
    .CMD_READY(),
    .CMD_START_FLAG()
    
);

genvar k;
generate
    for (k = 0; k < 4; k = k + 1) begin: cmd_diff_gen

        OBUFDS #(
            .IOSTANDARD("LVDS_25")
        ) OBUFDS_inst_refclock(
            .I(CMD_CLK[k])    , 
            .O(REFCLK_P[k])        ,
            .OB(REFCLK_N[k])
        );

        OBUFDS #(
            .IOSTANDARD("LVDS_25")
        ) OBUFDS_inst_cmd(
            .I(CMD_DATA[k])    , 
            .O(CMDDCI_P[k])    , 
            .OB(CMDDCI_N[k])
        );

    end
endgenerate


wire [1:0] NOT_CONNECTED_RX;
wire TLU_SEL, TDC_SEL;
wire [3:0] SEL;
gpio #(
    .BASEADDR(GPIO_RX_BASEADDR),
    .HIGHADDR(GPIO_RX_HIGHADDR),
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

wire [3:0] FE_FIFO_READ, FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA [3:0];
wire [3:0] RX_READY;

genvar i;
generate
  for (i = 0; i < 4; i = i + 1) begin: rx_gen
    wire dobout_s;
    IBUFDS #(
        .DIFF_TERM("TRUE")    ,
        .IOSTANDARD("LVDS_25")
    ) IBUFDS_inst_dobout(
        .I(DOBOUT_P[i])        , 
        .IB(DOBOUT_N[i])    , 
        .O(dobout_s)
    );
    
    fei4_rx 
    #(
        .BASEADDR(RX1_BASEADDR-32'h0100*i),
        .HIGHADDR(RX1_HIGHADDR-32'h0100*i),
        .DSIZE(10),
        .DATA_IDENTIFIER(i+1),
        .ABUSWIDTH(ABUSWIDTH),
        .USE_FIFO_CLK(1)
    ) i_fei4_rx (
        .RX_CLK(CLK160),
        .RX_CLK2X(CLK320),
        .DATA_CLK(CLK16),
        
        .RX_DATA(dobout_s),
        
        .RX_READY(RX_READY[i]),
        .RX_8B10B_DECODER_ERR(),
        .RX_FIFO_OVERFLOW_ERR(),
        
        .FIFO_CLK(CLK125),
        .FIFO_READ(FE_FIFO_READ[i]),
        .FIFO_EMPTY(FE_FIFO_EMPTY[i]),
        .FIFO_DATA(FE_FIFO_DATA[i]),
        
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

//more modules possible
wire TDC_FIFO_READ, TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
assign TDC_FIFO_EMPTY = 1;
        
wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;

rrp_arbiter 
#( 
    .WIDTH(5) // changed from 2
) i_rrp_arbiter
(
    .RST(BUS_RST),
    .CLK(CLK125),

    .WRITE_REQ({~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY & TDC_SEL}),
    .HOLD_REQ({5'b0}), // changed from 2 bit to 5 bit
    .DATA_IN({FE_FIFO_DATA[3],FE_FIFO_DATA[2],FE_FIFO_DATA[1], FE_FIFO_DATA[0], TDC_FIFO_DATA}),
    .READ_GRANT({FE_FIFO_READ[3], FE_FIFO_READ[2], FE_FIFO_READ[1], FE_FIFO_READ[0], TDC_FIFO_READ}),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign USR_CLK = !CLK125; //This can be worked out to change 

wire FIFO_EMPTY, FIFO_FULL;
fifo_32_to_8 #(.DEPTH(16*1024)) i_data_fifo (
    .RST(BUS_RST),
    .CLK(CLK125),
    
    .WRITE(ARB_WRITE_OUT),
    .READ(USR_TX_WE),
    .DATA_IN(ARB_DATA_OUT),
    .FULL(FIFO_FULL),
    .EMPTY(FIFO_EMPTY),
    .DATA_OUT(USR_TX_WD)
);
assign ARB_READY_OUT = !FIFO_FULL;
assign USR_TX_WE = !USR_TX_AFULL && !FIFO_EMPTY;

assign NIM_OUT = 0; //what is this
assign USR_CLOSE_ACK = USR_CLOSE_REQ;
assign USR_RX_RE = 1'b1;

assign LED[0] = RX_READY[0];
assign LED[1] = FIFO_EMPTY;
assign LED[2] = FIFO_FULL;
assign LED[7:3] = 5'b10101;

    
endmodule 