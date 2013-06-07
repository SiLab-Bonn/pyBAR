module debouncer
#(
    parameter COUNT_MAX = 40000 // clock cycles needed to accept button state
)
(
    input wire CLK,
    input wire PB, // "PB" is the glitched, asynchronous, active low push-button signal
    output reg PB_STATE, // state of the push-button (0 when up, 1 when down/active)
    output wire PB_UP, // 1 when the push-button goes down (just pushed)
    output wire PB_DOWN // 1 when the push-button goes up (just released)
);

// First use two flipflops to synchronize the PB signal the "CLK" clock domain
reg pb_sync_0;  always @(posedge CLK) pb_sync_0 <= ~PB;  // invert PB to make PB_sync_0 active high
reg pb_sync_1;  always @(posedge CLK) pb_sync_1 <= pb_sync_0;

// Next declare a 16-bits counter
integer pb_cnt;

// When the push-button is pushed or released, we increment the counter
// The counter has to be maxed out before we decide that the push-button state has changed

wire pb_idle = (PB_STATE==pb_sync_1) ? 1'b1 : 1'b0;
reg pb_cnt_max;

always @(posedge CLK)
if(pb_idle)
begin
    PB_STATE <= PB_STATE;
    pb_cnt_max <= 1'b0;
    pb_cnt <= 0; // nothing's going on
end
else
begin
    if(COUNT_MAX == pb_cnt)
    begin
        PB_STATE <= ~PB_STATE; // if the counter is maxed out, PB changed!
        pb_cnt_max <= 1'b1;
        pb_cnt <= pb_cnt;
    end
	else
	begin
        PB_STATE <= PB_STATE;
        pb_cnt_max <= 1'b0;
        pb_cnt <= pb_cnt + 1; // something's going on, increment the counter
    end
end

assign PB_DOWN = PB_STATE & ~pb_idle & pb_cnt_max; // true for one clock cycle when we detect that PB went down
assign PB_UP = ~PB_STATE & ~pb_idle & pb_cnt_max; // true for one clock cycle when we detect that PB went up

endmodule
