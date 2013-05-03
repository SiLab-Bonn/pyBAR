`timescale 1ps / 1ps
 //`default_nettype none

module top (
    
    input wire FCLK_IN, 
    
    //full speed 
    inout wire [7:0] DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FD,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //debug
    output wire [15:0] DEBUG_D,
    output wire LED1,
    output wire LED2,
    output wire LED3,
    output wire LED4,
    output wire LED5,
    
    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,
        
    input FE_RX,
    
    input CMD_EXT_START,
    output CMD_CLK,
    output CMD_DATA,
    output POWER_EN_VD1
    );   
    
    assign POWER_EN_VD1 = 1'b1;
    assign DEBUG_D = 16'ha5a5;
    assign {LED4, LED5}  = 0;

    
    wire BUS_CLK, BUS_CLK270;
    wire CLK_40;
    wire CLK_160;
    wire CLK_160_LOCKED;
    
    reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));
    
    clk_gen iclkgen(
         .CLKIN(FCLK_IN),
         .CLKINBUF(BUS_CLK),
         .CLKINBUF270(BUS_CLK270),
         .CLKOUT160(CLK_160),
         .CLKOUT40(CLK_40),
         .CLKOUT5(),
         .LOCKED(CLK_160_LOCKED)
    );
    
    wire [7:0] BUS_DATA_IN;
    assign BUS_DATA_IN = DATA;
    
    ///
    reg [7:0] DATA_OUT;
    
    reg [15:0] CMD_ADD;
    wire [7:0] CMD_BUS_DATA_OUT;
    reg CMD_BUS_RD, CMD_BUS_WR;

    reg [15:0] RX_ADD;
    wire [7:0] RX_BUS_DATA_OUT;
    reg RX_BUS_RD, RX_BUS_WR;
    
    reg [15:0] FIFO_ADD;
    wire [7:0] FIFO_BUS_DATA_OUT;
    reg FIFO_RD, FIFO_WR;
    
    wire [15:0] ADD_REAL;
    assign ADD_REAL = ADD - 16'h4000;
    
    always@(*) begin
        DATA_OUT = 0;
        
        CMD_ADD = 0;
        CMD_BUS_RD = 0;
        CMD_BUS_WR = 0;
        
        RX_BUS_RD = 0;
        RX_BUS_WR = 0;
        RX_ADD = 0;
        
        FIFO_ADD = 0;
        FIFO_RD = 0;
        FIFO_WR = 0;
        
        if( ADD_REAL < 16'h8000 ) begin
            CMD_BUS_RD = ~RD_B;
            CMD_BUS_WR = ~WR_B;
            CMD_ADD = ADD_REAL;
            DATA_OUT = CMD_BUS_DATA_OUT;
        end
        else if( ADD_REAL < 16'h8100 ) begin
            RX_BUS_RD = ~RD_B;
            RX_BUS_WR = ~WR_B;
            RX_ADD = ADD_REAL-16'h8000;
            DATA_OUT = RX_BUS_DATA_OUT;
        end
        else if( ADD_REAL < 16'h8200 ) begin
            FIFO_RD = ~RD_B;
            FIFO_WR = ~WR_B;
            FIFO_ADD = ADD_REAL-16'h8100;
            DATA_OUT = FIFO_BUS_DATA_OUT;
        end
        
    end
    
    assign DATA = ~RD_B ? DATA_OUT : 8'bzzzz_zzzz;
  
    cmd_seq icmd
    (
      .BUS_CLK(BUS_CLK),                     
      .BUS_RST(BUS_RST),                  
      .BUS_ADD(CMD_ADD),                    
      .BUS_DATA_IN(BUS_DATA_IN),                    
      .BUS_RD(CMD_BUS_RD),                    
      .BUS_WR(CMD_BUS_WR),                    
      .BUS_DATA_OUT(CMD_BUS_DATA_OUT),  
      
      .CMD_CLK_OUT(CMD_CLK),
      .CMD_CLK_IN(CLK_40),
      .CMD_EXT_START(CMD_EXT_START),
      .CMD_DATA(CMD_DATA)
    ); 
    
    
    wire FIFO_READ, FIFO_EMPTY;
    wire [31:0] FIFO_DATA;
    assign FIFO_DATA[31:24] = 8'b0;
    
    fei4_rx ifei4_rx(
    .RX_CLK(CLK_160),
    .RX_CLK_LOCKED(CLK_160_LOCKED),
    .RX_DATA(FE_RX),
    
    .RX_READY(LED1),
     
    .FIFO_READ(FIFO_READ),
    .FIFO_EMPTY(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA[23:0]),
     
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(RX_ADD),
    .BUS_DATA_IN(BUS_DATA_IN),
    .BUS_DATA_OUT(RX_BUS_DATA_OUT),
    .BUS_RST(BUS_RST),
    .BUS_WR(RX_BUS_WR),
    .BUS_RD(RX_BUS_RD)
    );
    
    wire USB_READ;
    assign USB_READ = FREAD && FSTROBE;
    out_fifo iout_fifo
    (
      .BUS_CLK(BUS_CLK),
      .BUS_CLK270(BUS_CLK270),
      .BUS_RST(BUS_RST),                  
      .BUS_ADD(FIFO_ADD),                    
      .BUS_DATA_IN(BUS_DATA_IN),                    
      .BUS_RD(FIFO_RD),                    
      .BUS_WR(FIFO_WR),                    
      .BUS_DATA_OUT(FIFO_BUS_DATA_OUT),  
      
      .SRAM_A(SRAM_A),
      .SRAM_IO(SRAM_IO),
      .SRAM_BHE_B(SRAM_BHE_B),
      .SRAM_BLE_B(SRAM_BLE_B),
      .SRAM_CE1_B(SRAM_CE1_B),
      .SRAM_OE_B(SRAM_OE_B),
      .SRAM_WE_B(SRAM_WE_B),
        
      .USB_READ(USB_READ),
      .USB_DATA(FD),
      
      .FIFO_READ_NEXT_OUT(FIFO_READ),
      .FIFO_EMPTY_IN(FIFO_EMPTY),
      .FIFO_DATA(FIFO_DATA),
      
      .FIFO_NOT_EMPTY(LED2),
      .FIFO_READ_ERROR(LED3)
    ); 
    
    
    `ifdef SYNTHESIS_NOT
    wire [35:0] control_bus;
    chipscope_icon ichipscope_icon
    (
        .CONTROL0(control_bus)
    ); 

    
    chipscope_ila ichipscope_ila 
    (
        .CONTROL(control_bus),
        //.CLK(BUS_CLK), 
        //.TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, ADD_REAL ,WR_B, RD_B})
		  .CLK(CLK_160), 
		  .TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, FE_RX ,WR_B, RD_B})
			
    ); 
    `endif

    
endmodule
