`timescale 1 ps / 1ps
`default_nettype none

module sync_slave_v2(
input wire          clk,                // clock input
input wire          clk90,              // clock 90 input
input wire  [1:0]   datain,             // data inputs
input wire          rst,                // reset input
input wire          usea,               // useA output for cascade
input wire          useb,               // useB output for cascade
input wire          usec,               // useC output for cascade
input wire          used,               // useD output for cascade
input wire  [1:0]   ctrl,               // ctrl outputs for cascade
output reg  [1:0]   sdataout );         // data out

wire         aa0 ;
wire         bb0 ;
wire         cc0 ;
wire         dd0 ;
reg         az2, bz2, cz2, dz2 ;
wire     [1:0]     az ;
wire     [1:0]     bz ;
wire     [1:0]     cz ;
wire     [1:0]     dz ;
wire         notclk ;
wire         notclk90 ;
wire      sdataa ;
wire      sdatab ;
wire     sdatac ;
wire     sdatad ;

assign notclk = ~clk ;
assign notclk90 = ~clk90 ;
assign sdataa = {(aa0 && usea)} ;
assign sdatab = {(bb0 && useb)} ;
assign sdatac = {(cc0 && usec)} ;
assign sdatad = {(dd0 && used)} ;

SRL16 saa0(.D(az2), .CLK(clk), .A0(ctrl[0]), .A1(ctrl[1]), .A2(1'b0), .A3(1'b0), .Q(aa0));
SRL16 sbb0(.D(bz2), .CLK(clk), .A0(ctrl[0]), .A1(ctrl[1]), .A2(1'b0), .A3(1'b0), .Q(bb0));
SRL16 scc0(.D(cz2), .CLK(clk), .A0(ctrl[0]), .A1(ctrl[1]), .A2(1'b0), .A3(1'b0), .Q(cc0));
SRL16 sdd0(.D(dz2), .CLK(clk), .A0(ctrl[0]), .A1(ctrl[1]), .A2(1'b0), .A3(1'b0), .Q(dd0));

always @ (posedge clk or posedge rst)
begin
if (rst) begin
    sdataout <= "11" ;
    az2 <= 1'b0 ; bz2 <= 1'b0 ; cz2 <= 1'b0 ; dz2 <= 1'b0 ;
end
else begin
    az2 <= az[1] ; bz2 <= bz[1] ; cz2 <= cz[1] ; dz2 <= dz[1] ;
    if (usea | useb | usec | used)
        sdataout <= sdataa | sdatab | sdatac | sdatad ;

end
end

// get all the samples into the same time domain

FDC ff_az0(.D(datain[0]), .C(clk),     .CLR(rst), .Q(az[0]))/*synthesis rloc = "x0y0" */;
FDC ff_az1(.D(az[0]),     .C(clk),     .CLR(rst), .Q(az[1]))/*synthesis rloc = "x2y0" */;

FDC ff_bz0(.D(datain[0]), .C(clk90),     .CLR(rst), .Q(bz[0]))/*synthesis rloc = "x1y0" */;
FDC ff_bz1(.D(bz[0]),     .C(clk),     .CLR(rst), .Q(bz[1]))/*synthesis rloc = "x4y0" */;

FDC ff_cz0(.D(datain[0]), .C(notclk),     .CLR(rst), .Q(cz[0]))/*synthesis rloc = "x1y1" */;
FDC ff_cz1(.D(cz[0]),     .C(clk),     .CLR(rst), .Q(cz[1]))/*synthesis rloc = "x2y0" */;

FDC ff_dz0(.D(datain[0]), .C(notclk90), .CLR(rst), .Q(dz[0]))/*synthesis rloc = "x0y1" */;
FDC ff_dz1(.D(dz[0]),     .C(clk90),     .CLR(rst), .Q(dz[1]))/*synthesis rloc = "x3y0" */;

endmodule
