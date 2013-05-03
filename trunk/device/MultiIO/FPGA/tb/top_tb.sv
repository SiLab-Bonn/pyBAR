`timescale 1ns / 1ps

////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer:
//
// Create Date:   21:17:20 03/23/2013
// Design Name:   top
// Module Name:   /faust/user/themperek/tmp/NTS/fpga/NTS/top_tb.v
// Project Name:  NTS
// Target Device:  
// Tool versions:  
// Description: 
//
// Verilog Test Fixture created by ISE for module: top
//
// Dependencies:
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
////////////////////////////////////////////////////////////////////////////////

`include "fei4_defines.sv"


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

 
 
`define CMD_BASE_ADD 16'h0000
`define CMD_START_REG `CMD_BASE_ADD+1
`define CMD_SIZE_REG `CMD_BASE_ADD+3
`define CMD_REP_REG `CMD_BASE_ADD+5
`define CMD_DATA_MEM `CMD_BASE_ADD+8

`define RX_BASE_ADD 16'h8000
`define RX_RESET_REG `RX_BASE_ADD

`define FIFO_BASE_ADD 16'h8100

module top_tb;

    // Inputs
    reg FCLK_IN;
    reg [15:0] ADD;
    reg RD_B;
    reg WR_B;
    reg FREAD;
    reg FSTROBE;
    reg FMODE;
    wire FE_RX;
    
    // Outputs
    wire [15:0] DEBUG_D;
    wire LED1;
    wire LED2;
    wire LED3;
    wire LED4;
    wire LED5;
    wire [19:0] SRAM_A;
    wire SRAM_BHE_B;
    wire SRAM_BLE_B;
    wire SRAM_CE1_B;
    wire SRAM_OE_B;
    wire SRAM_WE_B;

    // Bidirs
    wire [7:0] DATA_T;
    wire [7:0] FD;
    wire [15:0] SRAM_IO;

    wire CLK_160;
    wire CMD_CLK, CMD_DATA;
    
    // Instantiate the Unit Under Test (UUT)
    top uut (
        .FCLK_IN(FCLK_IN), 
        .DATA(DATA_T), 
        .ADD(ADD), 
        .RD_B(RD_B), 
        .WR_B(WR_B), 
        .FD(FD), 
        .FREAD(FREAD), 
        .FSTROBE(FSTROBE), 
        .FMODE(FMODE), 
        .DEBUG_D(DEBUG_D), 
        .LED1(LED1), 
        .LED2(LED2), 
        .LED3(LED3), 
        .LED4(LED4), 
        .LED5(LED5), 
        
        .SRAM_A(SRAM_A), 
        .SRAM_IO(SRAM_IO), 
        .SRAM_BHE_B(SRAM_BHE_B), 
        .SRAM_BLE_B(SRAM_BLE_B), 
        .SRAM_CE1_B(SRAM_CE1_B), 
        .SRAM_OE_B(SRAM_OE_B), 
        .SRAM_WE_B(SRAM_WE_B), 
        
        .FE_RX(FE_RX),
        
        .CMD_CLK(CMD_CLK),
        .CMD_DATA(CMD_DATA)
    
    );
   
   reg  RD1bar, RD2ENbar; 
   
    initial begin 
        RD1bar  = 0;
        RD2ENbar = 0;
        #3500  RD1bar  = 1;
        RD2ENbar = 1;
    end  
    
    reg [26880-1:0] hit;
    fei4_top fei4_inst (.RD1bar(RD1bar), .RD2ENbar(RD2ENbar), .clk_bc(CMD_CLK), .hit(hit), .DCI(CMD_DATA), .Ext_Trigger(1'b0), .ChipId(3'b000), .data_out(FE_RX) );
    
    reg [15:0] sram [1048576-1:0];
    //reg [15:0] sram [64-1:0];
    always@(posedge SRAM_WE_B)
        sram[SRAM_A] <= SRAM_IO;
    
    assign SRAM_IO = !SRAM_OE_B ? sram[SRAM_A] : 16'hzzzz;
    
    
    reg [7:0] DATA;
    assign DATA_T = ~WR_B ? DATA : 8'bzzzz_zzzz;
 
    cnfgreg_mem_t cnfg;
    logic [0:39][15:0] cnfg_reg;
    cnfgreg_address_t reg_address;
    assign cnfg_reg = cnfg; 
    initial cnfg = 0;
    
    task ReadExternal;
        input [15:0]  ADDIN;
        output [7:0]  DATAOUT;
        begin
            RD_B = 1;
            ADD = 16'hxxxx;
            repeat (5)
                @(posedge FCLK_IN);

            @(posedge FCLK_IN);
            ADD = ADDIN + 16'h4000;
            @(posedge FCLK_IN);
            RD_B = 0;
            @(posedge FCLK_IN);
            RD_B = 0;
            @(posedge FCLK_IN);
            DATAOUT = DATA_T;
            RD_B = 1;
            @(posedge FCLK_IN);
            RD_B = 1;
            ADD = 16'hxxxx;
            repeat (5)
                @(posedge FCLK_IN);
    
        end
    endtask
    
    task WriteExternal;
        input [15:0]  ADDIN;
        input [7:0]  DATAIN;
        begin
            WR_B = 1;
            ADD = 16'hxxxx;
            DATA = 16'hxxxx;
            repeat (5)
                @(posedge FCLK_IN);

            @(posedge FCLK_IN);
            ADD = ADDIN + 16'h4000;
            DATA = DATAIN;
            @(posedge FCLK_IN);
            WR_B = 0;
            @(posedge FCLK_IN);
            WR_B = 0;
            @(posedge FCLK_IN);
            WR_B = 1;
            @(posedge FCLK_IN);
            WR_B = 1;
            ADD = 16'hxxxx;
            DATA = 16'hxxxx;   
            repeat (5)
                @(posedge FCLK_IN);
    
        end
    endtask
    
    task WriteFeReg;
        input [5:0]  addressin;
        input [15:0]  datain;
        logic [0:4][7:0] reg_send;
        begin
            reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_WR_REG, 4'b0000, addressin, datain, 1'b0};
            
            WriteExternal( `CMD_SIZE_REG,  39);
            WriteExternal( `CMD_SIZE_REG+1 , 0 );
            
            WriteExternal( `CMD_DATA_MEM,    reg_send[0]);
            WriteExternal( `CMD_DATA_MEM+1,  reg_send[1]); 
            WriteExternal( `CMD_DATA_MEM+2,  reg_send[2]); 
            WriteExternal( `CMD_DATA_MEM+3,  reg_send[3]); 
            WriteExternal( `CMD_DATA_MEM+4,  reg_send[4]); 
            WriteExternal( `CMD_START_REG,  0);
        
            repeat (80) @(posedge FCLK_IN);
        
        end
    endtask
    
    task ReadFeReg;
        input [5:0]  addressin;
        logic [0:2][7:0] reg_send;
        begin
            reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_RD_REG, 4'b0000, addressin, 1'b0};
            WriteExternal( `CMD_SIZE_REG,  23);
            WriteExternal( `CMD_SIZE_REG+1 , 0 );
            
            WriteExternal( `CMD_DATA_MEM,    reg_send[0]);
            WriteExternal( `CMD_DATA_MEM+1,  reg_send[1]); 
            WriteExternal( `CMD_DATA_MEM+2,  reg_send[2]); 
            
            WriteExternal( `CMD_START_REG,  0);
            repeat (80) @(posedge FCLK_IN);
        end
    endtask
    
    task WriteFe;
        input [671:0]  datain;
        logic [0:86][7:0] reg_send;
        
        begin
            reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_WR_FE, 4'b0000, datain};
            
            WriteExternal( `CMD_SIZE_REG ,  689%256 );
            WriteExternal( `CMD_SIZE_REG+1 ,  689/256 );
            
            for(int i = 0; i < 87; i++) begin
                WriteExternal( `CMD_DATA_MEM +i, reg_send[i]);
            end
        
            WriteExternal( `CMD_START_REG,  0);
            repeat (1000) @(posedge FCLK_IN);
        
        end
    endtask
    
    
    
    task RunModeOn;
        begin
            WriteExternal( `CMD_SIZE_REG,  23);
            WriteExternal( `CMD_SIZE_REG+1 , 0 );
            
            WriteExternal( `CMD_DATA_MEM,    8'hb4);
            WriteExternal( `CMD_DATA_MEM+1,  8'h50);
            WriteExternal( `CMD_DATA_MEM+2,  8'h70);
            WriteExternal( `CMD_START_REG,  0);
            
            repeat (40) @(posedge FCLK_IN);
        end
    endtask
    
    task RunModeOff;
        begin
            WriteExternal( `CMD_SIZE_REG,  23);
            WriteExternal( `CMD_SIZE_REG+1 , 0 );
            
            WriteExternal( `CMD_DATA_MEM,    8'hb4);
            WriteExternal( `CMD_DATA_MEM+1,  8'h50);
            WriteExternal( `CMD_DATA_MEM+2,  8'h0e);
            WriteExternal( `CMD_START_REG,  0);
            
            repeat (40) @(posedge FCLK_IN);
        end
    endtask
    
    task GlobalPulse;
        begin
            WriteExternal( `CMD_SIZE_REG,  17);
            WriteExternal( `CMD_SIZE_REG+1 , 0 );
            
            WriteExternal( `CMD_DATA_MEM,    8'hb4);
            WriteExternal( `CMD_DATA_MEM+1,  8'h48);
            WriteExternal( `CMD_DATA_MEM+2,  8'h00);
            WriteExternal( `CMD_START_REG,  0);
            
            repeat (40) @(posedge FCLK_IN);
        end
    endtask
    
    
    task ReadFE;
        reg   [7:0] Data0;
        reg   [7:0] Data1;
        reg   [7:0] Data2;
        reg         Read_Fifo_Delayed;
        reg   [31:0] Pixel;
        reg		[31:0] Data_Count;
        reg					Head;
        reg		[7:0]	HeaderNumber;
        integer Results;
        
        begin
            @(posedge FCLK_IN);
            @(posedge FCLK_IN); #1 FREAD = 1; FSTROBE = 1;
            @(posedge FCLK_IN);
            #1 FREAD = 0; FSTROBE = 0;
            
            @(posedge FCLK_IN);
            @(posedge FCLK_IN); #1 FREAD = 1; FSTROBE = 1;
            @(posedge FCLK_IN)
                Data0 <= FD;
            #1 FREAD = 0; FSTROBE = 0;
    
            @(posedge FCLK_IN);
            @(posedge FCLK_IN); #1 FREAD = 1; FSTROBE = 1;
            @(posedge FCLK_IN)
                Data1 <= FD;
            #1 FREAD = 0; FSTROBE = 0;
            
            @(posedge FCLK_IN);
            @(posedge FCLK_IN); #1 FREAD = 1; FSTROBE = 1;
            @(posedge FCLK_IN)
                Data2 <= FD;
            #1 FREAD = 0; FSTROBE = 0;
            
            
           case ( Data0[7:0] )
			8'b11101001:					// Header
				begin
					HeaderNumber[7:0] <= HeaderNumber[7:0] + 8'h01;
					Data_Count[31:0] <= 32'd1;
					Head <= 1'b1;
					#5 $display ("\n Fifo(d) [%6d]: Header(d)[%2d]. BC(h) = [%3h], LV1Id(h)= [%2h], Serv_Word = [%1d]\n", Data_Count[31:0], HeaderNumber[7:0], { Data1[1:0], Data2[7:0] }, Data1[6:2], Data1[7] );
					#5 $fdisplay (Results,"\n Fifo(d) [%6d]: Header(d)[%2d]. BC(h) = [%3h], LV1Id(h)= [%2h], Serv_Word = [%1d]\n", Data_Count[31:0], HeaderNumber[7:0], { Data1[1:0], Data2[7:0] }, Data1[6:2], Data1[7] );
				end
			8'b11101010:					// Configuration address
				begin
					HeaderNumber[7:0] <= HeaderNumber[7:0];
					Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
					Head <= Head;
					#5 $display (" Fifo(d) [%6d]: Configuration address(d) = [%4d]\n", Data_Count[31:0], { Data1[7:0], Data2[7:0] } );
					#5 $fdisplay (Results," Fifo(d) [%6d]: Configuration address(d) = [%4d]\n", Data_Count[31:0], { Data1[7:0], Data2[7:0] } );
				end
			8'b11101100:					// Configuration Data      
				begin
					HeaderNumber[7:0] <= HeaderNumber[7:0];
					Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
					Head <= Head;
					#5 $display (" Fifo(d) [%6d]: Configuration Data(d)    = [%4x]\n", Data_Count[31:0], { Data1[7:0], Data2[7:0] } );
					#5 $fdisplay (Results," Fifo(d) [%6d]: Configuration Data(d)    = [%4d]\n", Data_Count[31:0], { Data1[7:0], Data2[7:0] } );
				end
			8'b11101111:					// Service Address
				begin
					HeaderNumber[7:0] <= HeaderNumber[7:0];
					case ( Data1[7:2] )
					6'b001001: begin 
												Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
												Head <= Head;
												#5 $display (" Fifo(d) [%6d]: Service Address(d) = 9 FifoFull(d) = [%3d]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:0] });
												#5 $fdisplay (Results," Fifo(d) [%6d]: Service Address(d) = 9 FifoFull(d) = [%3d]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:0] });
			 	  					 end
					
					6'b001110: begin 
												Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
												Head <= Head;
												#5 $display (" Fifo(d) [%6d]: Service Address = 14 LV1Id(h) = [%2h] BC(h) = [%3h]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:3] }, Data2[2:0]);
												#5 $fdisplay (Results," Fifo(d) [%6d]: Service Address = 14 LV1Id(h) = [%2h] BC(h) = [%3h]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:3] }, Data2[2:0]);
			 	  					 end
					6'b001111: begin
												Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
												Head <= Head;
												#5 $display (" Fifo(d) [%6d]: Service Address(d) = 15 Skipped(d) = [%3d]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:0] } );
												#5 $fdisplay (Results," Fifo(d) [%6d]: Service Address(d) = 15 Skipped(d) = [%3d]\n ", Data_Count[31:0], { Data1[1:0], Data2[7:0] } );
											end
					6'b010000: begin
											 if ( !Head ) begin Data_Count[31:0] <= 32'd1; $display ("\n"); end else Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
											 Head <= Head;											
											 #5 $display (" Fifo(d) [%6d]: Service Address(d) = 16 TF = [%1b] ETC(d) = %2d L1Req(h) = [%2h]\n ", Data_Count[31:0], Data1[1], { Data1[0], Data2[7:4] }, Data2[3:0] );
											 #5 $fdisplay (Results," Fifo(d) [%6d]: Service Address(d) = 16 TF = [%1b] ETC(d) = %2d L1Req(h) = [%2h]\n ", Data_Count[31:0], Data1[1], { Data1[0], Data2[7:4] }, Data2[3:0] );
										 end
					default:   begin
											 Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
											 Head <= 1'b0;
											 #5 $display (" Fifo(d) [%6d]: Service Address(d) = [%2d] Service Count(d) = [%3d]\n ", Data_Count[31:0], Data1[7:2], { Data1[1:0], Data2[7:0] } );
											 #5 $fdisplay (Results," Fifo(d) [%6d]: Service Address(d) = [%2d] Service Count(d) = [%3d]\n ", Data_Count[31:0], Data1[7:2], { Data1[1:0], Data2[7:0] } );
										 end
					endcase
				end
			default:
				begin
					HeaderNumber[7:0] <= HeaderNumber[7:0];
					Data_Count[31:0] <= Data_Count[31:0] + 32'd1;
					Head <= 1'b0;
					#5 $display (" Fifo [%6d]: Data: col=[%2d] row=[%3d] Tot=[%2d,%2d] (pix=[%5d,%5d])", Data_Count[31:0], Data0[7:1], { Data0[0] , Data1[7:0] },	Data2[7:4], Data2[3:0], Pixel, Pixel+1);
					#5 $fdisplay (Results," Fifo [%6d]: Data: col=[%2d] row=[%3d] Tot=[%2d,%2d] (pix=[%5d,%5d])", Data_Count[31:0], Data0[7:1], { Data0[0] , Data1[7:0] },	Data2[7:4], Data2[3:0], Pixel, Pixel+1);
				end
			endcase 
            
        end
    endtask
    
 
    initial begin
        // Initialize Inputs
        
        ADD = 16'h4000;
        RD_B = 1;
        WR_B = 1;
        FREAD = 0;
        FSTROBE = 0;
        FMODE = 0;
        hit = 0;
        // Wait 100 ns for global reset to finish
        #100;
        
        // Add stimulus here

    end
    
    initial begin
            FCLK_IN = 0;
            forever
                #(20.833/2) FCLK_IN =!FCLK_IN;
    end
    
    
    
    //initial begin
    //        FE_RX = 0;
    //end
    //always@(posedge uut.CLK_160)
    //    FE_RX <= !FE_RX;
    
    reg [23:0]  data_size ;
    
    initial begin
        repeat (250) @(posedge FCLK_IN);
        
        /*
        WriteExternal( `CMD_SIZE_REG,  11); //cmd pattern size
        WriteExternal( `CMD_REP_REG,  0); //cmd repeat 3 times
        
        //cmd pattern
        WriteExternal( `CMD_DATA_MEM,  8'b1000_0001);
        WriteExternal( `CMD_DATA_MEM+1,  8'b0111_1110);
        WriteExternal( `CMD_DATA_MEM+2,  8'b1010_0001);
        
        WriteExternal( `CMD_START_REG,  0); //cmd start
        
        repeat(200) @(posedge FCLK_IN);
        WriteExternal( `CMD_SIZE_REG,  11); //cmd pattern size
        WriteExternal( `CMD_REP_REG,  24); //cmd pattern size
        WriteExternal( `CMD_START_REG,  0); //cmd start
        */
        
        //reset - CMD_GPULSE
        GlobalPulse();
        
        //init PLL/DOB simulation
        
        cnfg.PllEn = 1; @(posedge FCLK_IN);
        WriteFeReg( 27 , cnfg_reg[27] );
        
        cnfg.PllEn40 = 1; cnfg.PllClk0S2 = 1; cnfg.PllEn160 = 1; @(posedge FCLK_IN);
        WriteFeReg( 28 , cnfg_reg[28] );

        WriteExternal( `CMD_BASE_ADD,  0);
        
        //run mode on
        RunModeOn();
        
        //ECR
        WriteExternal( `CMD_SIZE_REG,  9);
        WriteExternal( `CMD_DATA_MEM,    8'hb1);
        WriteExternal( `CMD_DATA_MEM+1,  8'h00);
        WriteExternal( `CMD_START_REG,  0);
        
        repeat (40) @(posedge FCLK_IN);
        
        //run mode off
        RunModeOff();
        
        
        //reset receiver to synchronize
        WriteExternal( `RX_RESET_REG,  0);
        
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
        WriteExternal( `CMD_SIZE_REG,  5);
        WriteExternal( `CMD_SIZE_REG+1 , 0 );
        WriteExternal( `CMD_DATA_MEM, {`CMD_LV1, 3'b0} );
        WriteExternal( `CMD_START_REG,  0);
      
        repeat (100) @(posedge FCLK_IN);
        
        #100000
        @(posedge FCLK_IN);
        
        ReadExternal( `FIFO_BASE_ADD + 1, data_size[7:0]);
        ReadExternal( `FIFO_BASE_ADD + 2, data_size[15:8]);
        ReadExternal( `FIFO_BASE_ADD + 3, data_size[23:16]);
        
        repeat (100) @(posedge FCLK_IN);
        
        for(int i=0; i< data_size/2; i++)
            ReadFE();
        
        ReadExternal( `FIFO_BASE_ADD + 1, data_size[7:0]);
        ReadExternal( `FIFO_BASE_ADD + 2, data_size[15:8]);
        ReadExternal( `FIFO_BASE_ADD + 3, data_size[23:16]);
        
        repeat (100) @(posedge FCLK_IN);
        
        for(int i=0; i< data_size/2; i++)
            ReadFE();
            
    end
    
    
    
    
endmodule

