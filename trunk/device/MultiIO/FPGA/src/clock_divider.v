
// clock devider generating clock and clock enable 

module clock_divider
#(
    parameter DIVISOR = 40000000
)
(
    input wire		CLK,
	input wire		RESET,
	output reg		CE_1HZ, // for sequential logic driven by CLK
	output reg		CLK_1HZ // only for combinatorial logic, do not waste bufg
);

integer counter_ce;
integer counter_clk;

// 1Hz clock enable
always @ (posedge CLK or posedge RESET)
	begin
		if (RESET == 1'b1)
			begin
				CE_1HZ <= 1'b0;
			end
		else
			begin
				if (counter_ce == 0)
					begin
						CE_1HZ <= 1'b1;
					end
				else
					begin
						CE_1HZ <= 1'b0;
					end
			end
	end
	
always @ (posedge CLK or posedge RESET)
	begin
		if (RESET == 1'b1)
			begin
				counter_ce <= 0;
			end
		else
			begin
				if (counter_ce == (DIVISOR - 1))
					counter_ce <= 0;
				else
					counter_ce <= counter_ce + 1;
			end
	end

// 1Hz clock
always @ (posedge CLK or posedge RESET)
	begin
		if (RESET == 1'b1)
			begin
				CLK_1HZ <= 1'b0;
			end
		else
			begin
				if (counter_clk == 0)
					begin
						CLK_1HZ <= ~CLK_1HZ;
					end
				else
					begin
						CLK_1HZ <= CLK_1HZ;
					end
			end
	end
	
always @ (posedge CLK or posedge RESET)
	begin
		if (RESET == 1'b1)
			begin
				counter_clk <= 0;
			end
		else
			begin
				if (counter_clk == ((DIVISOR >> 1) - 1)) // DIVISOR/2
					counter_clk <= 0;
				else
					counter_clk <= counter_clk + 1;
			end
	end

endmodule
