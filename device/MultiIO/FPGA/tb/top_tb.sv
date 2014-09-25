`timescale 1ns / 1ps

`include "silbusb.sv"

`include "fei4_defines.sv"

// FE commands
`define CMD_LV1 5'b11101
`define CMD_FIELD1 5'b10110

`define CMD_BCR 4'b0001
`define CMD_ECR 4'b0010
`define CMD_CAL 4'b0100
`define CMD_FIELD2 4'b1000

`define CMD_RD_REG 4'b0001
`define CMD_WR_REG 4'b0010
`define CMD_WR_FE 4'b0100
`define CMD_GRST 4'b1000
`define CMD_GPULSE  4'b1001
`define CMD_RUNMODE  4'b1010

 // CMD
`define CMD_BASE_ADD 16'h0000
`define CMD_START_REG `CMD_BASE_ADD+1
`define CMD_MODE_REG `CMD_MODE_ADD+2
`define CMD_SIZE_REG `CMD_BASE_ADD+3 // 16bit
`define CMD_REP_REG `CMD_BASE_ADD+5 // 32bit
`define CMD_START_REPEAT_REG `CMD_BASE_ADD+9 // 16bit
`define CMD_STOP_REPEAT_REG `CMD_BASE_ADD+11 // 16bit
`define CMD_DATA_MEM `CMD_BASE_ADD+16

// Rx
`define RX_BASE_ADD 16'h8000
`define RX_RESET_REG `RX_BASE_ADD

// FIFO
`define FIFO_BASE_ADD 16'h8100

module top_tb;

    // Inputs
    wire FCLK_IN;
    wire FE_RX;
    reg [2:0] LEMO_RX;
    reg RJ45_RESET;
    reg RJ45_TRIGGER;
    reg MONHIT;
    
    // Outputs
    wire [2:0] TX; // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    wire [4:0] LED;
    wire [19:0] SRAM_A;
    wire SRAM_BHE_B;
    wire SRAM_BLE_B;
    wire SRAM_CE1_B;
    wire SRAM_OE_B;
    wire SRAM_WE_B;

    // Bidirs
    wire [15:0] SRAM_IO;

    wire CLK_160;
    wire CMD_CLK, CMD_DATA;
    wire DOBOUT;
    
    SiLibUSB sidev(FCLK_IN);
    
    // Instantiate the Unit Under Test (UUT)
    reg FCLK_IN_IN;
    assign #1ns FCLK_IN = FCLK_IN_IN;

    top uut (
        .FCLK_IN(FCLK_IN_IN),
        .BUS_DATA(sidev.DATA), 
        .ADD(sidev.ADD), 
        .RD_B(sidev.RD_B), 
        .WR_B(sidev.WR_B), 
        .FDATA(sidev.FD), 
        .FREAD(sidev.FREAD), 
        .FSTROBE(sidev.FSTROBE), 
        .FMODE(sidev.FMODE),
        
        .MONHIT(MONHIT),
        
        .LED(LED),
        
        .SRAM_A(SRAM_A), 
        .SRAM_IO(SRAM_IO), 
        .SRAM_BHE_B(SRAM_BHE_B), 
        .SRAM_BLE_B(SRAM_BLE_B), 
        .SRAM_CE1_B(SRAM_CE1_B), 
        .SRAM_OE_B(SRAM_OE_B), 
        .SRAM_WE_B(SRAM_WE_B), 
        
        .DOBOUT({4{DOBOUT}}),
        
        .CMD_CLK(CMD_CLK),
        .CMD_DATA(CMD_DATA),
    
        .LEMO_RX(LEMO_RX),
        .TX(TX),
        .RJ45_RESET(RJ45_RESET),
        .RJ45_TRIGGER(RJ45_TRIGGER)
    
    );
   
   assign #0ns DOBOUT = FE_RX;
   
    //FEI4 Reset
    reg  RD1bar, RD2ENbar; 
   
    initial begin 
        RD1bar  = 0;
        RD2ENbar = 0;
        #3500  RD1bar  = 1;
        RD2ENbar = 1;
    end  
   
    
    //FEI4 Model
    reg [26880-1:0] hit;
    fei4_top fei4_inst (.RD1bar(RD1bar), .RD2ENbar(RD2ENbar), .clk_bc(CMD_CLK), .hit(hit), .DCI(CMD_DATA), .Ext_Trigger(1'b0), .ChipId(3'b000), .data_out(FE_RX) );
    
    `include "fei4_cmd.sv"
    
    
    //SRAM Model
    reg [15:0] sram [1048576-1:0];
    //reg [15:0] sram [64-1:0];
    always@(negedge SRAM_WE_B)
        sram[SRAM_A] <= SRAM_IO;
    
    assign SRAM_IO = !SRAM_OE_B ? sram[SRAM_A] : 16'hzzzz;
    
    //FEI3 configuration map
    cnfgreg_mem_t cnfg;
    logic [0:39][15:0] cnfg_reg;
    cnfgreg_address_t reg_address;
    assign cnfg_reg = cnfg; 
    initial cnfg = 0;
        

    initial begin
        hit = 0;
        FCLK_IN_IN = 0;
        forever
            #(20.833/2) FCLK_IN_IN =!FCLK_IN_IN;
    end
    
    reg [23:0]  data_size ;
    
    initial begin
        LEMO_RX = 0;
        RJ45_RESET = 0;
        RJ45_TRIGGER = 0;
        MONHIT = 0;
        
        repeat (300) @(posedge FCLK_IN);
        
        /*
        sidev.WriteExternal( `CMD_SIZE_REG,  11); //cmd pattern size
        sidev.WriteExternal( `CMD_REP_REG,  0); //cmd repeat 3 times
        
        //cmd pattern
        sidev.WriteExternal( `CMD_DATA_MEM,  8'b1000_0001);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'b0111_1110);
        sidev.WriteExternal( `CMD_DATA_MEM+2,  8'b1010_0001);
        
        sidev.WriteExternal( `CMD_START_REG,  0); //cmd start
        
        repeat(200) @(posedge FCLK_IN);
        sidev.WriteExternal( `CMD_SIZE_REG,  11); //cmd pattern size
        sidev.WriteExternal( `CMD_REP_REG,  24); //cmd pattern size
        sidev.WriteExternal( `CMD_START_REG,  0); //cmd start
        */
        
        //reset - CMD_GPULSE
        GlobalPulse();
        
        //init PLL/DOB simulation
        
        cnfg.PllEn = 1; @(posedge FCLK_IN);
        WriteFeReg( 27 , cnfg_reg[27] );
        
        cnfg.PllEn40 = 1; cnfg.PllClk0S2 = 1; cnfg.PllEn160 = 1; @(posedge FCLK_IN);
        WriteFeReg( 28 , cnfg_reg[28] );

        sidev.WriteExternal( `CMD_BASE_ADD,  0);
        
        //run mode on
        RunModeOn();
        
        //ECR
        sidev.WriteExternal( `CMD_SIZE_REG,  9);
        sidev.WriteExternal( `CMD_DATA_MEM,    8'hb1);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'h00);
        sidev.WriteExternal( `CMD_START_REG,  0);
        
        repeat (40) @(posedge FCLK_IN);
        
        //run mode off
        RunModeOff();
        
        
        //reset receiver to synchronize
        sidev.WriteExternal( `RX_RESET_REG,  0);
        
        repeat (300) @(posedge FCLK_IN);
        #200000
        
        
        ReadFeReg( 0 );
        ReadFeReg( 27 );

        repeat (150) @(posedge FCLK_IN);
        
        
        ReadFE();
        ReadFE();
        
        
        cnfg.ConfAddrEnable = 1 ; @(posedge FCLK_IN);
        WriteFeReg( 2 , cnfg_reg[2] );
        
        ReadFeReg( 2 );
        ReadFeReg( 28 );
        
        ReadFE();
        ReadFE();
        ReadFE();
        ReadFE();
        
        //set latency

        //enable all columns
        cnfg.CnfgMode = 2'b11;
        cnfg.ColAddrSel = 6'd0; @(posedge FCLK_IN);
        WriteFeReg( 21 , cnfg_reg[12] );

   	    cnfg.SrClr = 'b1; @(posedge FCLK_IN);
        WriteFeReg( 27 , cnfg_reg[27] );
           
        //reset - CMD_GPULSE
        GlobalPulse();
        
        cnfg.SrClr = 'b0; @(posedge FCLK_IN);
        WriteFeReg( 27 , cnfg_reg[27] );
        
        WriteFe(-1);
        
        
        cnfg.PxStrobes = '1; @(posedge FCLK_IN);
        WriteFeReg( 13 , cnfg_reg[13] );
        
        cnfg.LatchEn =1; @(posedge FCLK_IN);
        WriteFeReg( 27 , cnfg_reg[27] );
       
        GlobalPulse();
       
        
        cnfg.LatCnfg = 100; @(posedge FCLK_IN);
        WriteFeReg( 25 , cnfg_reg[25] );
         
        cnfg.TrigCnt = '1; @(posedge FCLK_IN);
        WriteFeReg( 2 , cnfg_reg[2] );
        
        //run mode on
        RunModeOn();
        
        repeat (50) @(posedge FCLK_IN);
        hit = ~hit;
        repeat (4) @(posedge FCLK_IN);
        hit = 0;
        
        repeat (105) @(posedge FCLK_IN);
        
        //send trigger
        sidev.WriteExternal( `CMD_SIZE_REG, 5);
        sidev.WriteExternal( `CMD_SIZE_REG+1, 0);
        sidev.WriteExternal( `CMD_DATA_MEM, {`CMD_LV1, 3'b0});
        sidev.WriteExternal( `CMD_START_REG,  0);
        
        repeat (100) @(posedge FCLK_IN);

        sidev.WriteExternal( `CMD_SIZE_REG, 5);
        sidev.WriteExternal( `CMD_SIZE_REG+1, 0 );
        sidev.WriteExternal( `CMD_REP_REG, 1 );
        sidev.WriteExternal( 16'h8200+1,  2); // set trigger mode
        sidev.WriteExternal( 16'h8200+2,  144); // set trigger clock cycles, and write timestamp
        sidev.WriteExternal( 16'h0000+2,  1); // enable ext command
        
        sidev.WriteExternal( 16'h8700+1,  5); // TDC start
        #50000
        MONHIT = 1;
        #150
        MONHIT = 0;
        #500 MONHIT = 1;
        #152 MONHIT = 0;
        #494 MONHIT = 1; // small ToT: overlapping two data words
        #7 MONHIT = 0;
        #489 MONHIT = 1; // small ToT: at the end of data
        #7 MONHIT = 0;
        #489 MONHIT = 1; // small ToT: middle of data
        #7 MONHIT = 0;
        #500 MONHIT = 1; // overflow
        #8192 MONHIT = 0;
        #500 MONHIT = 1;
        #12 MONHIT = 0;
        #500 MONHIT = 1;
        #40 MONHIT = 0;
        #10000
        @(posedge FCLK_IN);

        
        #20000
        RJ45_TRIGGER = 1;
        #60
        RJ45_TRIGGER = 0;
        #80000
        @(posedge FCLK_IN);
        
        sidev.ReadExternal( `FIFO_BASE_ADD + 1, data_size[7:0]);
        sidev.ReadExternal( `FIFO_BASE_ADD + 2, data_size[15:8]);
        sidev.ReadExternal( `FIFO_BASE_ADD + 3, data_size[23:16]);
        
        repeat (100) @(posedge FCLK_IN);
        
        for(int i=0; i< data_size/2; i++)
            ReadFE();
        
        sidev.ReadExternal( `FIFO_BASE_ADD + 1, data_size[7:0]);
        sidev.ReadExternal( `FIFO_BASE_ADD + 2, data_size[15:8]);
        sidev.ReadExternal( `FIFO_BASE_ADD + 3, data_size[23:16]);
        
        repeat (100) @(posedge FCLK_IN);
        
        for(int i=0; i< data_size/2; i++)
            ReadFE();


        // CMD
        repeat(2000) @(posedge FCLK_IN);
        sidev.WriteExternal( `CMD_SIZE_REG,  64);
        sidev.WriteExternal( `CMD_REP_REG,  2);
        sidev.WriteExternal( `CMD_DATA_MEM,    8'h81);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'hc1);
        sidev.WriteExternal( `CMD_DATA_MEM+2,  8'hFF);
        sidev.WriteExternal( `CMD_DATA_MEM+3,  8'h00);
        sidev.WriteExternal( `CMD_DATA_MEM+4,  8'hFF);
        sidev.WriteExternal( `CMD_DATA_MEM+5,  8'hAA);
        sidev.WriteExternal( `CMD_DATA_MEM+6,  8'h55);
        sidev.WriteExternal( `CMD_DATA_MEM+7,  8'hFF);
        
        sidev.WriteExternal( `CMD_START_REPEAT_REG, 0); // 16bit
        sidev.WriteExternal( `CMD_STOP_REPEAT_REG, 0); // 16bit
        sidev.WriteExternal( `CMD_START_REG,  0);
        repeat(200) @(posedge FCLK_IN);

        sidev.WriteExternal( `CMD_START_REPEAT_REG, 8); // 16bit
        sidev.WriteExternal( `CMD_STOP_REPEAT_REG, 0); // 16bit
        sidev.WriteExternal( `CMD_START_REG,  0);
        repeat(200) @(posedge FCLK_IN);
        
        sidev.WriteExternal( `CMD_START_REPEAT_REG, 8); // 16bit
        sidev.WriteExternal( `CMD_STOP_REPEAT_REG, 16); // 16bit
        sidev.WriteExternal( `CMD_START_REG,  0);
        repeat(200) @(posedge FCLK_IN);
    end
    
    
    
    
endmodule

