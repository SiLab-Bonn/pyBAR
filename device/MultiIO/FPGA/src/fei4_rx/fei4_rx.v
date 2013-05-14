module fei4_rx
(
    input RX_CLK,
    input RX_CLK_LOCKED,
    input RX_DATA,
    output RX_READY,
     
    input FIFO_READ,
    output FIFO_EMPTY,
    output [31:0] FIFO_DATA,
    
    output RX_FIFO_FULL,

    input BUS_CLK,
    input [15:0] BUS_ADD,
    input [7:0] BUS_DATA_IN,
    output reg [7:0] BUS_DATA_OUT,
    input BUS_RST,
    input BUS_WR,
    input BUS_RD
);

wire [23:0] FE_DATA;
assign FIFO_DATA = {8'b0000_0000, FE_DATA};

// 0 - soft reset
// 1 - status
// 2-3 fifo size
// 4 - code_err_cnt
// 5 - lost_err_cnt

wire SOFT_RST;
assign SOFT_RST = (BUS_ADD==0 && BUS_WR);

wire [15:0] fifo_size;
wire [7:0] code_err_cnt, lost_err_cnt;
wire phase_align_error;
wire [7:0] eye_size, search_size;

always @ (negedge BUS_CLK) begin //(*) begin
    //BUS_DATA_OUT = 0;

    if(BUS_ADD == 1)
        BUS_DATA_OUT <= {6'b0, phase_align_error, RX_READY};
    else if(BUS_ADD == 2)
        BUS_DATA_OUT <= fifo_size[7:0];
    else if(BUS_ADD == 3)
        BUS_DATA_OUT <= fifo_size[15:8];
    else if(BUS_ADD == 4)
        BUS_DATA_OUT <= code_err_cnt;
    else if(BUS_ADD == 5)
        BUS_DATA_OUT <= lost_err_cnt;
    else if(BUS_ADD == 6)
        BUS_DATA_OUT <= eye_size;
    else if(BUS_ADD == 7)
        BUS_DATA_OUT <= search_size;
    else
        BUS_DATA_OUT <= 0;
end

wire RST;
assign RST = BUS_RST | SOFT_RST;

wire ready_rec;
assign RX_READY = ready_rec && code_err_cnt == 0;

receiver_logic ireceiver_logic (
    .bus_reset(RST),
    .ioclk(RX_CLK),
    .bus_clk(BUS_CLK),
    .read(FIFO_READ),
    .data(FE_DATA),
    .empty(FIFO_EMPTY),
    .full(RX_FIFO_FULL),
    .ready(ready_rec),
    .rx(RX_DATA),
    .lost_err_cnt(lost_err_cnt),
    .code_err_cnt(code_err_cnt),
    .fifo_size(fifo_size),
    .phase_align_error(phase_align_error),
    .eye_size(eye_size),
    .search_size(search_size)
);

endmodule
