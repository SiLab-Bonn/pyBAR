/**
* ------------------------------------------------------------
* Copyright (c) SILAB , Physics Institute of Bonn University 
* ------------------------------------------------------------
*
* SVN revision information:
*  $Rev:: 33                    $:
*  $Author:: themperek          $: 
*  $Date:: 2013-09-12 12:06:48 #$:
*/

task WriteFeReg;
    input [5:0]  addressin;
    input [15:0]  datain;
    logic [0:4][7:0] reg_send;
    begin
        reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_WR_REG, 4'b0000, addressin, datain, 1'b0};
        
        sidev.WriteExternal( `CMD_SIZE_REG,  39);
        sidev.WriteExternal( `CMD_SIZE_REG+1 , 0 );
        
        sidev.WriteExternal( `CMD_DATA_MEM,    reg_send[0]);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  reg_send[1]); 
        sidev.WriteExternal( `CMD_DATA_MEM+2,  reg_send[2]); 
        sidev.WriteExternal( `CMD_DATA_MEM+3,  reg_send[3]); 
        sidev.WriteExternal( `CMD_DATA_MEM+4,  reg_send[4]); 
        sidev.WriteExternal( `CMD_START_REG,  0);
    
        repeat (80) @(posedge FCLK_IN);
    
    end
endtask

task ReadFeReg;
    input [5:0]  addressin;
    logic [0:2][7:0] reg_send;
    begin
        reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_RD_REG, 4'b0000, addressin, 1'b0};
        sidev.WriteExternal( `CMD_SIZE_REG,  23);
        sidev.WriteExternal( `CMD_SIZE_REG+1 , 0 );
        
        sidev.WriteExternal( `CMD_DATA_MEM,    reg_send[0]);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  reg_send[1]); 
        sidev.WriteExternal( `CMD_DATA_MEM+2,  reg_send[2]); 
        
        sidev.WriteExternal( `CMD_START_REG,  0);
        repeat (80) @(posedge FCLK_IN);
    end
endtask

task WriteFe;
    input [671:0]  datain;
    logic [0:86][7:0] reg_send;
    
    begin
        reg_send = {`CMD_FIELD1, `CMD_FIELD2, `CMD_WR_FE, 4'b0000, datain};
        
        sidev.WriteExternal( `CMD_SIZE_REG ,  689%256 );
        sidev.WriteExternal( `CMD_SIZE_REG+1 ,  689/256 );
        
        for(int i = 0; i < 87; i++) begin
            sidev.WriteExternal( `CMD_DATA_MEM +i, reg_send[i]);
        end
    
        sidev.WriteExternal( `CMD_START_REG,  0);
        repeat (1000) @(posedge FCLK_IN);
    
    end
endtask



task RunModeOn;
    begin
        sidev.WriteExternal( `CMD_SIZE_REG,  23);
        sidev.WriteExternal( `CMD_SIZE_REG+1 , 0 );
        
        sidev.WriteExternal( `CMD_DATA_MEM,    8'hb4);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'h50);
        sidev.WriteExternal( `CMD_DATA_MEM+2,  8'h70);
        sidev.WriteExternal( `CMD_START_REG,  0);
        
        repeat (40) @(posedge FCLK_IN);
    end
endtask

task RunModeOff;
    begin
        sidev.WriteExternal( `CMD_SIZE_REG,  23);
        sidev.WriteExternal( `CMD_SIZE_REG+1 , 0 );
        
        sidev.WriteExternal( `CMD_DATA_MEM,    8'hb4);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'h50);
        sidev.WriteExternal( `CMD_DATA_MEM+2,  8'h0e);
        sidev.WriteExternal( `CMD_START_REG,  0);
        
        repeat (40) @(posedge FCLK_IN);
    end
endtask

task GlobalPulse;
    begin
        sidev.WriteExternal( `CMD_SIZE_REG,  17);
        sidev.WriteExternal( `CMD_SIZE_REG+1 , 0 );
        
        sidev.WriteExternal( `CMD_DATA_MEM,    8'hb4);
        sidev.WriteExternal( `CMD_DATA_MEM+1,  8'h48);
        sidev.WriteExternal( `CMD_DATA_MEM+2,  8'h00);
        sidev.WriteExternal( `CMD_START_REG,  0);
        
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
    bit [31:0] sram_data;
    
    begin
        sidev.FastBlockRead(sram_data[31:24]);
        sidev.FastBlockRead(sram_data[23:16]); 
        sidev.FastBlockRead(sram_data[15:8]);
        sidev.FastBlockRead(sram_data[7:0]);

        Data0 = sram_data[23:16];
        Data1 = sram_data[15:8];
        Data2 = sram_data[7:0];
        
       $display (" Data - %h - id = %d", sram_data, sram_data[31:24]); 
       if(sram_data[31:28] == 4'b0100 ) begin
            $display (" TDC - %d - id=%d\n", sram_data[11:0], sram_data[27:12] ); 
       end
       else begin
           case ( Data0[7:0] )
            8'b11101001:					// Header
                begin
                    HeaderNumber[7:0] <= HeaderNumber[7:0] + 8'h01;
                    Data_Count[31:0] <= 32'd1;
                    Head <= 1'b1;
                    #5 $display (" Fifo(d) [%6d]: Header(d)[%2d]. BC(h) = [%3h], LV1Id(h)= [%2h], Serv_Word = [%1d]\n", Data_Count[31:0], HeaderNumber[7:0], { Data1[1:0], Data2[7:0] }, Data1[6:2], Data1[7] );
                    #5 $fdisplay (Results," Fifo(d) [%6d]: Header(d)[%2d]. BC(h) = [%3h], LV1Id(h)= [%2h], Serv_Word = [%1d]\n", Data_Count[31:0], HeaderNumber[7:0], { Data1[1:0], Data2[7:0] }, Data1[6:2], Data1[7] );
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
    end
endtask


