`timescale 1ns / 1ps

// synchronizing asynchronous signals/flags, prevents metastable events

module two_stage_synchronizer(
	input wire		CLK_IN,
	input wire		CLK_OUT,
	input wire		IN,
	output reg		OUT
);

reg out_d_ff;

always @(posedge CLK_IN) // first stage
	begin
		out_d_ff <= IN;
	end

always @(posedge CLK_OUT) // second stage
	begin
		OUT <= out_d_ff;
	end

endmodule
