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

`timescale 1ns / 1ps

`include "fei4_top.sv"

module tb(
    input wire FCLK_IN, 

    //full speed 
    inout wire [7:0] BUS_DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FD,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE
);

    // Inputs
    wire FE_RX;
    reg RJ45_RESET;
    reg RJ45_TRIGGER;
    reg MONHIT;
    reg TRIG;
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

    wire REF_CLK, CMD_DATA;
    wire DOBOUT;
    
    top fpga (

        .FCLK_IN(FCLK_IN),
        
        .BUS_DATA(BUS_DATA), 
        .ADD(ADD), 
        .RD_B(RD_B), 
        .WR_B(WR_B), 
        .FDATA(FD), 
        .FREAD(FREAD), 
        .FSTROBE(FSTROBE), 
        .FMODE(FMODE),
        
        .LEMO_RX({MONHIT,1'b0, TRIG}),
        
        .LED(LED),
        
        .SRAM_A(SRAM_A), 
        .SRAM_IO(SRAM_IO), 
        .SRAM_BHE_B(SRAM_BHE_B), 
        .SRAM_BLE_B(SRAM_BLE_B), 
        .SRAM_CE1_B(SRAM_CE1_B), 
        .SRAM_OE_B(SRAM_OE_B), 
        .SRAM_WE_B(SRAM_WE_B), 
        
        .DOBOUT({4{DOBOUT}}),
        
        .REF_CLK(REF_CLK),
        .CMD_DATA(CMD_DATA),
    
        .TX(TX),
        .RJ45_RESET(RJ45_RESET),
        .RJ45_TRIGGER(RJ45_TRIGGER)
    
    );
   
    assign DOBOUT = FE_RX;
   
    //FEI4 Reset
    reg  RD1bar, RD2ENbar; 
   
    initial begin 
        RD1bar  = 0;
        RD2ENbar = 0;
        #3500  RD1bar  = 1;
        RD2ENbar = 1;
    end  
   
    initial begin
        $dumpfile("tb.vcd");
        $dumpvars(0);
    end 
    
    //FEI4 Model
    reg [26880-1:0] hit;
    fei4_top fei4_inst (.RD1bar(RD1bar), .RD2ENbar(RD2ENbar), .clk_bc(REF_CLK), .hit(hit), .DCI(CMD_DATA), .Ext_Trigger(1'b0), .ChipId(3'b000), .data_out(FE_RX) );
    
    
    //SRAM Model
    reg [15:0] sram [1048576-1:0];
    //reg [15:0] sram [64-1:0];
    always@(negedge SRAM_WE_B)
        sram[SRAM_A] <= SRAM_IO;
    
    assign SRAM_IO = !SRAM_OE_B ? sram[SRAM_A] : 16'hzzzz;
    
    initial begin
        hit = 0;
    end
    
endmodule

