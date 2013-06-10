
`timescale 1ps/1ps

module rec_sync (
    pll_rst,
    reset,
    datain,
    wclk, ioclk,
    ready, data, 
    phase_align_error, eye_size, search_size, pll_lck
);

parameter DSIZE = 10;

input pll_rst, reset;
input datain;
input ioclk;
output wclk;
output ready;
output [DSIZE-1:0] data;
output phase_align_error, pll_lck;
output [7:0] eye_size, search_size;

wire bitslip, pa_ready, pll_lock;
phase_align #(
    .DSIZE(DSIZE)
    ) iphase_align (
    .PLL_RST(pll_rst),
    .DATA_IN(datain),
    .DATA_OUT(data),
    .IO_CLK(ioclk),
    .RESET(reset),
    .WCLK(wclk),
    .BITSLIP(bitslip),
    .ERROR(phase_align_error),
    .READY(pa_ready),
    .EYE_SIZE(eye_size),
    .SEARCH_SIZE(search_size),
    .lck(pll_lck)
);

wire RST;
assign RST = reset | !pll_lck;

integer wait_cnt;
reg [1:0] state, next_state;

localparam START  = 0, WAIT = 1, CHECK = 2, READY = 3;

localparam   K28_1P = 10'b00_1111_1001,
             K28_1N = 10'b11_0000_0110;

//always @ (posedge wclk_bufg)
always @ (posedge wclk)
  begin : FSM_SEQ
    if (RST) begin
      state <= START;
    end else begin
      state <=   next_state;
    end
 end

// this maybe can be simplified (only PAHSE0 and PHASE1)
always @ (*) begin
    next_state = state;
    
    case(state)
        START : 
            if(pa_ready)
                next_state = WAIT;
            else
                next_state = START;

        WAIT:
            if(wait_cnt > 7)
                next_state = CHECK;
            else
                next_state = WAIT;

        CHECK: 
            if(data == K28_1P || data == K28_1N)
                next_state = READY;
            else
                next_state = START;

        READY:
            next_state = READY;
            
        default : next_state = START;
    endcase
end

always @ (posedge wclk) begin
    if (RST || state==START )
        wait_cnt <= 0;
    else if(state==WAIT)
        wait_cnt <=  wait_cnt +1;
    else
        wait_cnt <= 0;
end

assign bitslip = (state==CHECK && next_state==START);
assign ready = (state==READY);


`ifdef SYNTHESIS_NOT
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
);

chipscope_ila ichipscope_ila 
(
    .CONTROL(control_bus),
    .CLK(wclk), 
    .TRIG0({lck, eye_size, phase_align_error, data, bitslip, state, pa_ready, reset, pll_rst}) 
);
`endif

endmodule
