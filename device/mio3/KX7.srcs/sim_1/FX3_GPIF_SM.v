`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 02/07/2014 05:41:56 PM
// Design Name: 
// Module Name: FX3_GPIF_SM
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////


module FX3_GPIF_SM(
    input  wire [31:0] count,
    input  wire [31:0] addr,
    input  wire [31:0] wr_data,
    input  wire [31:0] data_size,
    input  wire read_write_n,
    output reg  [31:0]rd_data,
    output reg  [31:0]data_counter,
    input  wire trg,
    output reg idle,
    input  wire clk,
    input  wire rst,
//    output reg fx3_aden,
//    output reg fx3_counten,
//    output reg fx3_rd,
    output reg fx3_wr,
    output reg fx3_oe,
    output reg fx3_cs,
    output wire fx3_rst,
    input  wire fx3_rdy,
    input  wire fx3_valid,
    inout  wire [31:0]fx3_bus
    );
    
 
   	reg [31:0] fx3_bus_reg;  // to simulate bidir bus
	  assign fx3_bus = fx3_oe? 32'dz : fx3_bus_reg;  // to simulate bidir bus
	  
//	  reg [31:0] request_counter = 32'b0;

    
    
    assign fx3_rst = rst;
    
       parameter IDLE     = 8'b00000001;
       parameter ADDR     = 8'b00000010;
       parameter WRITE    = 8'b00000100;
       parameter WR_WAIT  = 8'b00001000;
       parameter READ     = 8'b00010000;
       parameter RD_WAIT  = 8'b00100000;
       parameter COUNT    = 8'b01000000;
       parameter NOP2     = 8'b10000000;
    
       reg [7:0] state = IDLE;
    
       always @(posedge clk or posedge rst)
       begin
          if (rst) begin
             state <= IDLE;
             data_counter <= 32'b0; //?
//             fx3_aden <= 1'b0;
//             fx3_counten <= 1'b0;
//             fx3_rd   <= 1'b0;
             fx3_wr   <= 1'b0;
             fx3_oe   <= 1'b0;
             fx3_cs   <= 1'b0;
             idle     <= 1'b0;
//             request_counter <= 32'b0;
          end
          else
//             fx3_aden <= 1'b0;
//             fx3_counten <= 1'b0;
//             fx3_rd   <= 1'b0;
             fx3_wr   <= 1'b0;
             fx3_oe   <= 1'b0;
             fx3_cs   <= 1'b0;
             idle     <= 1'b0;

             case (state)
                IDLE : begin
                   if (trg)
                   begin
                      fx3_cs <= 1'b1; // SOF
                      state <= ADDR;
                      data_counter <= 0;
//                      request_counter <= 32'b0;
                   end
                   else
                      state <= IDLE;
                      idle     <= 1'b1;
                   end
                ADDR : begin
                   fx3_bus_reg <= addr;   
                   //fx3_aden <= 1'b1;
                   fx3_cs <= 1'b1;
                   state <= COUNT;
                end
                WRITE : begin
                   if (data_counter == (data_size /*+ 2*/)) // 2 last words appear on the ddr3_dq_sdram
                   begin
                     /*repeat (2) @(posedge clk)
                        fx3_wr <= 1'b1;*/
                     state <= IDLE;
                   end
                   else
                   begin
                     if (fx3_rdy)
                     begin
                        fx3_wr <= 1'b1;
                        fx3_bus_reg <= wr_data;
                        data_counter <= data_counter + 1;
                        state <= WRITE;
                     end
                     else
                        state <= WR_WAIT;
                   end
                   fx3_cs <= 1'b1;
                end
                WR_WAIT : begin
                 if (data_counter == data_size)
                   state <= IDLE;
                 else
                 begin
                   if (fx3_rdy) 
                   begin
                      state <= WRITE;
                      fx3_wr <= 1'b1;
                      fx3_bus_reg <= wr_data;
                      data_counter <= data_counter + 1;
                   end
                   else
                      state <= WR_WAIT;
                 end
                 fx3_cs <= 1'b1;
                end
                READ : begin
                if (data_counter == data_size) // not == 0
                  state <= IDLE;
                else
                begin
                if (fx3_valid)
                begin
//                 fx3_rd <= 1'b1;
                   rd_data <= fx3_bus;
                   data_counter <= data_counter + 1;
                   state <= READ;
                end
                else
                   state <= RD_WAIT;
                end
//                fx3_rd <= 1'b1;
                fx3_cs <= 1'b1;
                fx3_oe <= 1'b1;
                end
                RD_WAIT : begin
                  if (data_counter == data_size) // not == 0
                    state <= IDLE;
                  else
                  begin
                    if (fx3_valid)
                    begin
                       state <= READ;
                       rd_data <= fx3_bus;
                       data_counter <= data_counter + 1;
//                       fx3_rd <= 1'b1;
                    end
                    else
                       state <= RD_WAIT;
                  end
//                fx3_rd <= 1'b1;
                fx3_cs <= 1'b1;
                fx3_oe <= 1'b1;
                end
                COUNT : begin
                  fx3_bus_reg <= count;
                  //fx3_counten <= 1'b1;
                  fx3_cs <= 1'b1;
                  if (read_write_n)
                  begin 
                    if (fx3_valid)
                    begin
                      state <= READ;
                      /*rd_data <= fx3_bus;
                      data_counter <= data_counter + 1;
                      fx3_oe <= 1'b1;*/
                    end
                    else
                      state <= RD_WAIT;
                  end
                  else  // write access
                  begin
                    if (fx3_rdy)
                    begin
                        state <= WRITE;
                        /*fx3_wr <= 1'b1;
                        fx3_bus_reg <= wr_data;
                        data_counter <= data_counter + 1;*/ // Add write here?
                    end
                    else
                      state <= WR_WAIT; 
                  end
                end
                NOP2 : begin
 
                    state <= IDLE;
                 end
                default: begin  // Fault Recovery
                   state <= IDLE;
    	         end
             endcase
 end   							
    							    
    
endmodule
