/*******************************************************************************
*                                                                              *
* System      : SiTCP                                                          *
* Block       : SIO                                                            *
* Module      : SIO_SLAVE                                                     *
* Version     : v 0.0.0 2008/03/26 12:01                                       *
*                                                                              *
* Description : A sample for the Serial IO interface                           *
*                                                                              *
* Designer    : Tomohisa Uchida                                                *
*                                                                              *
*                Copyright (c) 2008 Tomohisa Uchida                            *
*                All rights reserved                                           *
*                                                                              *
*******************************************************************************/
module slave(
RSTn,	// in	: System reset
FILL_ADDR,	// in	: Filled address for narow address-width
// Serial I/F
SCK,	// in	: Clock
SCS,	// in	: Active
SI,	// out	: Data input
SO,	// in	: Data output
// Register I/F
REG_ADDR,	// out	: Address[31:0]
REG_WD,	// out	: Data[7:0]
REG_WE,	// out	: Write enable
REG_RE,	// out	: Read enable
REG_ACK,	// in	: Access acknowledge
REG_RV,	// in	: Read valid
REG_RD	// in	: Read data[7:0]
);

//-------- Input/Output -------------
input RSTn;
input [31:0] FILL_ADDR;

output [31:0] REG_ADDR;
output [7:0] REG_WD;
output REG_WE;
output REG_RE;
input REG_ACK;
input REG_RV;
input [7:0]	REG_RD;

input SCK;
input SCS;
output SI;
input SO;

//---------- Buffer ----------
wire [31:0] REG_ADDR;
wire [7:0] REG_WD;
wire REG_WE;
wire REG_RE;
wire SI;

//------------------------------------------------------------------------------
//	Receive
//------------------------------------------------------------------------------
reg [47:0] recvBuf;
reg [7:0] recvCmd;
wire stopShft;
reg waitAck;

always@ (posedge SCK or negedge SCS) begin
if(~SCS)
begin
  recvBuf[47:0] <= 48'd0;
  recvCmd[7:0] <= 8'd0;
  waitAck <= 1'b0;
end 
else begin
  recvBuf[47:0] <= (stopShft ? recvBuf[47:0]	: {recvBuf[46:0],SO});
  recvCmd[7:0]	<= (recvCmd[7] ? recvCmd[ 7:0] : {recvCmd[ 6:0],SO});
  waitAck <= stopShft;
end
end

wire [2:0] stopBitSel;

assign stopBitSel[2:0] = {recvCmd[5],recvCmd[3:2]};

assign stopShft = ((stopBitSel[2:0]==3'b000) ? recvBuf[23] : 1'b0)|
						((stopBitSel[2:0]==3'b001) ? recvBuf[31] : 1'b0)|
						((stopBitSel[2:0]==3'b010) ? recvBuf[39] : 1'b0)|
						((stopBitSel[2:0]==3'b011) ? recvBuf[47] : 1'b0)|
						((stopBitSel[2:0]==3'b100) ? recvBuf[15] : 1'b0)|
						((stopBitSel[2:0]==3'b101) ? recvBuf[23] : 1'b0)|
						((stopBitSel[2:0]==3'b110) ? recvBuf[31] : 1'b0)|
						((stopBitSel[2:0]==3'b111) ? recvBuf[39] : 1'b0);

// Write and Read enables
reg orRegWe;
reg orRegRe;

always@ (posedge SCK or negedge SCS) begin
if(~SCS)
begin
  orRegWe <= 1'b0;
  orRegRe <= 1'b0;
end 
else 
begin
  orRegWe <= stopShft & ~waitAck & ~recvCmd[5];
  orRegRe <= stopShft & ~waitAck &  recvCmd[5];
end
end

assign REG_WE = orRegWe;
assign REG_RE = orRegRe;

// Address and write data
reg [31:0] orRegAddr;
reg [7:0] orRegWd;

always@ (posedge SCK) begin
case(stopBitSel[2:0])
3'd0: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31: 8],recvBuf[15:8]};
  orRegWd[7:0]	<= recvBuf[7:0];
  end
3'd1: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31:16],recvBuf[23:8]};
  orRegWd[7:0]	<= recvBuf[7:0];
  end
3'd2: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31:24],recvBuf[31:8]};
  orRegWd[7:0]	<= recvBuf[7:0];
  end
3'd3: begin
  orRegAddr[31:0]	<= recvBuf[39:8];
  orRegWd[7:0]	<= recvBuf[7:0];
  end
3'd4: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31: 8],recvBuf[7:0]};
  orRegWd[7:0]	<= 8'd0;
  end
3'd5: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31:16],recvBuf[15:0]};
  orRegWd[7:0]	<= 8'd0;
  end
3'd6: begin
  orRegAddr[31:0]	<= {FILL_ADDR[31:24],recvBuf[23:0]};
  orRegWd[7:0]	<= 8'd0;
  end
default: begin
  orRegAddr[31:0]	<= recvBuf[31:0];
  orRegWd[7:0]	<= 8'd0;
  end
endcase
end

assign REG_ADDR[31:0] = orRegAddr[31:0];
assign REG_WD[7:0] = orRegWd[7:0];

//------------------------------------------------------------------------------
//	Send
//------------------------------------------------------------------------------
reg waitEnd;
reg [8:0] sendBuf;

always@ (posedge SCK or negedge SCS) begin
if(~SCS)
begin
  waitEnd <= 1'b0;
  sendBuf[8:0] <= 9'd0;
end 
else 
begin
  waitEnd <= (REG_ACK ? 1'b1 : waitEnd);
  sendBuf[8] <= REG_ACK | sendBuf[7];
  sendBuf[7:0] <= (REG_ACK	? (REG_RV ? REG_RD[7:0]	: 8'hFF) : {sendBuf[6:0],waitEnd});
end
end

assign SI = sendBuf[8];

//------------------------------------------------------------------------------
endmodule
