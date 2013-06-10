module receiver_logic (
    bus_reset,
    ioclk,
    bus_clk,
    read,
    data,
    empty,
    full,
    ready,
    rx,
    lost_err_cnt,
    code_err_cnt,
    fifo_size,
    phase_align_error,
    eye_size,
    search_size
);

input bus_reset, ioclk, bus_clk, read, rx;
output  empty, full, ready;
output [23:0] data;
output reg [7:0] lost_err_cnt, code_err_cnt;
output [15:0] fifo_size;

output phase_align_error;
output [7:0] eye_size, search_size;

//generate sync long reset
wire reset_rec_sync;
reg [5:0] rst_cnt;
always@(posedge bus_clk) begin
    if(bus_reset)
        rst_cnt <= 5'd8;
    else if(rst_cnt != 5'd7)
        rst_cnt <= rst_cnt +1;
end

wire rst_long = rst_cnt[5];

wire wclk;

reg cdc_sync_ff;
always @(posedge wclk) begin
    cdc_sync_ff <= rst_long;
end

wire pll_lck;

assign reset_rec_sync = cdc_sync_ff | !pll_lck;

wire write_8b10b;
wire [9:0] data_8b10b;

rec_sync irec_sync (
    .pll_rst(bus_reset),
    .reset(reset_rec_sync),
    .datain(rx),
    .wclk(wclk),
    .ioclk(ioclk),
    .ready(ready),
    .data(data_8b10b),
    .phase_align_error(phase_align_error),
    .eye_size(eye_size),
    .search_size(search_size),
    .pll_lck(pll_lck)
);

assign write_8b10b = ready;

reg [9:0] data_to_dec;
wire dec_k, code_err;
wire [7:0] dec_data;

integer i;
always @ (*) begin
    for (i=0; i<10; i=i+1)
      data_to_dec[(10-1)-i] = data_8b10b[i];
end

reg dispin;
wire dispout;
always@(posedge wclk) begin
    if(reset_rec_sync)
        dispin <= !dispout;
    else if(write_8b10b)
        dispin <= !dispout;
end

decode_8b10b decode_8b10b_inst (
    .datain(data_to_dec),
    .dispin(dispin),
    .dataout({dec_k,dec_data}),
    .dispout(dispout),
    .code_err(code_err),
    .disp_err()
);

always@(posedge wclk) begin
    if(reset_rec_sync)
        code_err_cnt <= 0;
    else if(code_err && write_8b10b && code_err_cnt != 8'hff)
        code_err_cnt <= code_err_cnt + 1;
end

reg [2:0] byte_sel;
always@(posedge wclk) begin
    if(reset_rec_sync || (write_8b10b && dec_k) || (write_8b10b && dec_k==0 && byte_sel==2))
        byte_sel <= 0;
    else if(write_8b10b)
        byte_sel <= byte_sel + 1;
end

reg [7:0] data_dec_in [2:0];
always@(posedge wclk) begin
    if(write_8b10b && dec_k==0)
        data_dec_in[byte_sel] <= dec_data;
end

reg write_dec_in; 
always@(posedge wclk) begin
    if(write_8b10b && dec_k==0 && byte_sel==2)
        write_dec_in <= 1;
    else
        write_dec_in <= 0;
end

wire cdc_fifo_full, cdc_fifo_empty;

always@(posedge wclk) begin
    if(reset_rec_sync)
        lost_err_cnt <=0;
    else if(cdc_fifo_full && write_dec_in && lost_err_cnt != 8'hff)
        lost_err_cnt <= lost_err_cnt +1;
end

wire [23:0] cdc_data_out;
//wire full;
wire [23:0] wdata;
assign  wdata = {data_dec_in[0],data_dec_in[1],data_dec_in[2]};

cdc_syncfifo #(
    .DSIZE(24),
    .ASIZE(2)
) cdc_syncfifo_i (
    .rdata(cdc_data_out),
    .wfull(cdc_fifo_full),
    .rempty(cdc_fifo_empty),
    .wdata(wdata),
    .winc(write_dec_in),
    .wclk(wclk),
    .wrst(reset_rec_sync),
    .rinc(!full),
    .rclk(bus_clk),
    .rrst(rst_long)
);

gerneric_fifo #(
    .DATA_SIZE(24),
    .DEPTH(2048)
) fifo_i (
    .clk(bus_clk),
    .reset(rst_long),
    .write(!cdc_fifo_empty),
    .read(read),
    .data_in(cdc_data_out),
    .full(full),
    .empty(empty),
    .data_out(data), 
    .size(fifo_size)
);

`ifdef SYNTHESIS_NOT
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
);

chipscope_ila ichipscope_ila 
(
    .CONTROL(control_bus),
    //.CLK(bus_clk), 
    //.TRIG0({ ready, reset_rec_sync, cdc_sync_ff ,rst_cnt, bus_reset})
    .CLK(wclk), 
    .TRIG0({ cdc_fifo_full, wdata ,write_8b10b ,write_dec_in, reset_rec_sync, rst_cnt, cdc_sync_ff})
);
`endif

endmodule
