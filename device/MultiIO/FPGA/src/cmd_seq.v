
module cmd_seq
(
    BUS_CLK,
    BUS_RST,
    BUS_ADD,
    BUS_DATA_IN,
    BUS_RD,
    BUS_WR,
    BUS_DATA_OUT,
    
    CMD_CLK_OUT,
    CMD_CLK_IN,
    CMD_EXT_START_FLAG,
    CMD_EXT_START_ENABLE,
    CMD_DATA,
    CMD_READY
); 



parameter OUT_LINES = 1;

input                       BUS_CLK;
input                       BUS_RST;
input      [15:0]           BUS_ADD;
input      [7:0]            BUS_DATA_IN;
input                       BUS_RD;
input                       BUS_WR;
output reg [7:0]            BUS_DATA_OUT;

input CMD_CLK_IN;
input CMD_EXT_START_FLAG;
output CMD_EXT_START_ENABLE;
output CMD_DATA;
output CMD_CLK_OUT;
output CMD_READY;


wire SOFT_RST; //0
wire START, CONF_FINISH; //1
wire CONF_EN_EXT_START, CONF_EN_CLOCK_GATE, CONF_EN_NEGEDGE_DATA; //, CONF_EN_EXT_NEGEDGE; //2
wire [15:0] CONF_CMD_SIZE; //3 - 4
wire [15:0] CONF_REPEAT_COUNT; //5 - 6

reg [7:0] status_regs[7:0];

wire RST;
assign RST = BUS_RST || SOFT_RST;


always @(posedge BUS_CLK) begin
    if(RST) begin
        status_regs[0] <= 0;
        status_regs[1] <= 0;
        status_regs[2] <= 8'b0000_0010; //invert clock out
        status_regs[3] <= 0;
        status_regs[4] <= 0;
        status_regs[5] <= 8'd1; //repeat once
        status_regs[6] <= 0;
        status_regs[7] <= 0;
    end
    else if(BUS_WR && BUS_ADD < 8)
        status_regs[BUS_ADD[2:0]] <= BUS_DATA_IN;
end

assign SOFT_RST = (BUS_ADD==0 && BUS_WR);
assign START = (BUS_ADD==1 && BUS_WR);

assign CONF_CMD_SIZE = {status_regs[4], status_regs[3]};
assign CONF_REPEAT_COUNT = {status_regs[6], status_regs[5]};

//assign CONF_EN_EXT_NEGEDGE = status_regs[2][3];
assign CONF_EN_CLOCK_GATE = status_regs[2][2]; // no clock domain crossing needed
assign CONF_EN_NEGEDGE_DATA = status_regs[2][1]; // no clock domain crossing needed
assign CONF_EN_EXT_START = status_regs[2][0];

three_stage_synchronizer conf_ena_ext_start_sync (
    .CLK(CMD_CLK_IN),
    .IN(CONF_EN_EXT_START),
    .OUT(CMD_EXT_START_ENABLE)
);


(* RAM_STYLE="{AUTO | BLOCK |  BLOCK_POWER1 | BLOCK_POWER2}" *)
reg [7:0] cmd_mem [2047:0];
always @(posedge BUS_CLK) begin
    if (BUS_WR && BUS_ADD >= 8)
        cmd_mem[BUS_ADD[10:0]-8] <= BUS_DATA_IN;
    
    if(BUS_ADD == 1)
        BUS_DATA_OUT <= {7'b0, CONF_FINISH};
    else if(BUS_ADD < 8)
        BUS_DATA_OUT <= status_regs[BUS_ADD[2:0]];
    else
        BUS_DATA_OUT <= cmd_mem[BUS_ADD[10:0]-8];
end

reg [7:0] CMD_MEM_DATA;
reg [10:0] CMD_MEM_ADD;
always @(posedge CMD_CLK_IN)
    CMD_MEM_DATA <= cmd_mem[CMD_MEM_ADD];

// start sync
// when wite to addr = 1 then send command

// reg [3:0] write_start;
// always@(posedge BUS_CLK) begin
    // if(RST)
        // write_start <= 0;
    // else if(START)
        // write_start <= 5'd4;
    // else if(write_start != 5'd3)
        // write_start <= write_start +1;
// end

// reg bus_start_sync, start_sync_ff, start_sync_ff2, start_sync_ff3;
// wire start_sync;
// always @(posedge BUS_CLK) 
    // bus_start_sync <= write_start[3];

// always @(posedge CMD_CLK_IN) begin
    // start_sync_ff <= bus_start_sync;
    // start_sync_ff2 <= start_sync_ff;
    // start_sync_ff3 <= start_sync_ff2;
// end

// assign start_sync = ~start_sync_ff3 && start_sync_ff2;

reg START_FF;
always @(posedge BUS_CLK)
    START_FF <= START;

wire START_FLAG;
assign START_FLAG = ~START_FF & START;

wire start_sync;
flag_domain_crossing cmd_start_flag_domain_crossing (
    .CLK_A(BUS_CLK),
    .CLK_B(CMD_CLK_IN),
    .FLAG_IN_CLK_A(START_FLAG),
    .FLAG_OUT_CLK_B(start_sync)
);


// reset sync

// reg [3:0] write_reset;
// always@(posedge BUS_CLK) begin
    // if(RST)
        // write_reset <= 5'd4;
    // else if(write_reset != 5'd3)
        // write_reset <= write_reset +1;
// end

// reg bus_reset_sync, rst_sync_ff, reset_sync;
// always @(posedge BUS_CLK) 
    // bus_reset_sync <= write_reset[3];

// always @(posedge CMD_CLK_IN) begin
    // rst_sync_ff <= bus_reset_sync;
    // reset_sync <= rst_sync_ff;
// end

reg RST_FF;
always @(posedge BUS_CLK)
    RST_FF <= RST;

wire RST_FLAG;
assign RST_FLAG = ~RST_FF & RST;

wire reset_sync;
flag_domain_crossing cmd_rst_flag_domain_crossing (
    .CLK_A(BUS_CLK),
    .CLK_B(CMD_CLK_IN),
    .FLAG_IN_CLK_A(RST_FLAG),
    .FLAG_OUT_CLK_B(reset_sync)
);


wire ext_send_cmd;
assign ext_send_cmd = (CMD_EXT_START_FLAG & CMD_EXT_START_ENABLE);
wire send_cmd;
assign send_cmd = start_sync | ext_send_cmd;

localparam WAIT = 1, SEND = 2;

reg [15:0] cnt;
reg [15:0] repeat_cnt;
reg [2:0] state, next_state;

always @ (posedge CMD_CLK_IN)
    if (reset_sync)
      state <= WAIT;
    else
      state <= next_state;
  
always @ (*) begin
    case(state)
        WAIT : if(send_cmd)
                    next_state = SEND;
                else
                    next_state = WAIT;
        SEND : if(cnt == CONF_CMD_SIZE && repeat_cnt==CONF_REPEAT_COUNT)
                    next_state = WAIT;
                else
                    next_state = SEND;
        default : next_state = WAIT;
    endcase
end
  

always @ (posedge CMD_CLK_IN) begin
    if (reset_sync)
        cnt <= 0;
    else if(state != next_state)
        cnt <= 0;
    else if(cnt == CONF_CMD_SIZE)
        cnt <= 1;    
    else
        cnt <= cnt +1;
end

always @ (posedge CMD_CLK_IN) begin
    if (send_cmd || reset_sync)
        repeat_cnt <= 1;
    else if(state == SEND && cnt == CONF_CMD_SIZE && repeat_cnt != 16'hffff)
        repeat_cnt <= repeat_cnt + 1;
end


always @ (*) begin
    if(state != next_state && next_state == SEND)
        CMD_MEM_ADD = 0;
    else if(state == SEND)
        if(cnt == CONF_CMD_SIZE-1)
            CMD_MEM_ADD = 0;
        else
            CMD_MEM_ADD = (cnt+1)/8;
    else
        CMD_MEM_ADD = 0; //no latch
end

reg [7:0] send_word;

always @ (posedge CMD_CLK_IN) begin
    if(reset_sync)
        send_word <= 0;
    else if(state == SEND) begin
        if(next_state == WAIT)
            send_word <= 0; //this is streange -> bug of FEI4 ?
        else if(cnt == CONF_CMD_SIZE)
            send_word <= CMD_MEM_DATA;
        else if(cnt %8 == 0)
            send_word <= CMD_MEM_DATA;
        else
            send_word[7:0] <= {send_word[6:0],send_word[0]};
    end
end



reg cmd_data_neg;
reg cmd_data_pos;
always @ (negedge CMD_CLK_IN)
cmd_data_neg <= send_word[7];

always @ (posedge CMD_CLK_IN)
cmd_data_pos <= send_word[7];

//assign CMD_DATA =  send_word[7];
assign CMD_DATA = CONF_EN_NEGEDGE_DATA ? cmd_data_neg : cmd_data_pos;

//assign CMD_CLK_OUT = CONF_EN_NEGEDGE_DATA ? ~CMD_CLK_IN : CMD_CLK_IN; //TODO: enable/inverse (this should be some clock with 180 from DCM!)
//BUFGCE BUFGCE_inst ( .O(CMD_CLK_OUT),  .CE(CONF_EN_CLOCK_GATE && ), .I(CMD_CLK_IN) );
assign CMD_CLK_OUT = CMD_CLK_IN;

// reeady sync 
reg ready_sync_in;
always @ (posedge CMD_CLK_IN) 
    ready_sync_in <= (state == WAIT);

// reg ready_sync_ff, ready_sync;
// always @(posedge BUS_CLK) begin
    // ready_sync_ff <= ready_sync_in;
    // ready_sync <= ready_sync_ff;
// end

wire ready_sync;
three_stage_synchronizer ready_signal_sync (
    .CLK(BUS_CLK),
    .IN(ready_sync_in),
    .OUT(ready_sync)
);

assign CONF_FINISH = ready_sync;
assign CMD_READY = ready_sync_in;
  
    
endmodule
