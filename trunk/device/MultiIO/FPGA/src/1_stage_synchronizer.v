`timescale 1ns / 1ps

// synchronizing data crossing clock damains with same frequency (and fixed phase relationship)

module one_stage_synchronizer(
	input wire		CLK,
	input wire		IN,
	output reg		OUT
);

always @(posedge CLK)
	begin
		OUT <= IN;
	end

endmodule
