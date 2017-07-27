/**
 * This file is part of pyBAR.
 * 
 * pyBAR is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * pyBAR is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 * 
 * You should have received a copy of the GNU Lesser General Public License
 * along with pyBAR.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */

`timescale 1ns / 1ps
`default_nettype none

module clk_gen (
    U1_CLKIN_IN, 
    U1_USER_RST_IN,  
    U1_CLKIN_IBUFG_OUT, 
    U1_CLK0_OUT, 
    U1_STATUS_OUT, 
    U2_CLKFX_OUT, 
    U2_CLKDV_OUT, 
    U2_CLK0_OUT, 
    U2_CLK2X_OUT, 
    U2_LOCKED_OUT, 
    U2_STATUS_OUT
);

input wire U1_CLKIN_IN;
input wire U1_USER_RST_IN;
output wire U2_CLKFX_OUT;
output wire U1_CLKIN_IBUFG_OUT;
output wire U1_CLK0_OUT;
output wire [7:0] U1_STATUS_OUT;
output wire U2_CLKDV_OUT;
output wire U2_CLK0_OUT;
output wire U2_CLK2X_OUT;
output wire U2_LOCKED_OUT;
output wire [7:0] U2_STATUS_OUT;

wire GND_BIT;
wire U1_CLKIN_IBUFG;
wire U1_CLK0_BUF;
wire U1_LOCKED_INV_IN;
wire U1_RST_IN;
wire U2_CLKDV_BUF;
wire U2_CLKFB_IN;
wire U2_CLKFX_BUF;
wire U2_CLK0_BUF;
wire U2_CLK2X_BUF;
wire U2_LOCKED_INV_RST;
wire U2_RST_IN;
wire CLKFX_OUT;
wire CLKFX_OUT_IBUFG;

assign GND_BIT = 0;
assign U1_CLKIN_IBUFG_OUT = U1_CLKIN_IBUFG;
assign U2_CLK0_OUT = U2_CLKFB_IN;
DCM #( .CLK_FEEDBACK("1X"), .CLKDV_DIVIDE(4.0), .CLKFX_DIVIDE(3), 
    .CLKFX_MULTIPLY(10), .CLKIN_DIVIDE_BY_2("FALSE"), 
    .CLKIN_PERIOD(20.833), .CLKOUT_PHASE_SHIFT("NONE"), 
    .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), .DFS_FREQUENCY_MODE("LOW"), 
    .DLL_FREQUENCY_MODE("LOW"), .DUTY_CYCLE_CORRECTION("TRUE"), 
    .FACTORY_JF(16'h8080), .PHASE_SHIFT(0), .STARTUP_WAIT("FALSE") ) 
    DCM_INST1 (
        .CLKFB(U1_CLK0_OUT), 
        .CLKIN(U1_CLKIN_IBUFG), // 48MHz
        .DSSEN(GND_BIT), 
        .PSCLK(GND_BIT), 
        .PSEN(GND_BIT), 
        .PSINCDEC(GND_BIT), 
        .RST(U1_RST_IN), 
        .CLKDV(), 
        .CLKFX(CLKFX_OUT), 
        .CLKFX180(), 
        .CLK0(U1_CLK0_BUF), 
        .CLK2X(), 
        .CLK2X180(), 
        .CLK90(), 
        .CLK180(), 
        .CLK270(), 
        .LOCKED(U1_LOCKED_INV_IN), 
        .PSDONE(), 
        .STATUS(U1_STATUS_OUT[7:0]));
DCM #( .CLK_FEEDBACK("1X"), .CLKDV_DIVIDE(10.0), .CLKFX_DIVIDE(8), 
    .CLKFX_MULTIPLY(2), .CLKIN_DIVIDE_BY_2("FALSE"), 
    .CLKIN_PERIOD(6.250), .CLKOUT_PHASE_SHIFT("NONE"), 
    .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), .DFS_FREQUENCY_MODE("LOW"), 
    .DLL_FREQUENCY_MODE("LOW"), .DUTY_CYCLE_CORRECTION("TRUE"), 
    .FACTORY_JF(16'h8080), .PHASE_SHIFT(0), .STARTUP_WAIT("FALSE") ) 
    DCM_INST2 (
        .CLKFB(U2_CLKFB_IN), 
        .CLKIN(CLKFX_OUT_IBUFG), // 160MHz
        .DSSEN(GND_BIT), 
        .PSCLK(GND_BIT), 
        .PSEN(GND_BIT), 
        .PSINCDEC(GND_BIT), 
        .RST(U2_RST_IN), 
        .CLKDV(U2_CLKDV_BUF), 
        .CLKFX(U2_CLKFX_BUF), 
        .CLKFX180(), 
        .CLK0(U2_CLK0_BUF), 
        .CLK2X(U2_CLK2X_BUF), 
        .CLK2X180(), 
        .CLK90(), 
        .CLK180(), 
        .CLK270(), 
        .LOCKED(U2_LOCKED_OUT), 
        .PSDONE(), 
        .STATUS(U2_STATUS_OUT[7:0]));
IBUFG  U1_CLKIN_IBUFG_INST (.I(U1_CLKIN_IN), 
                          .O(U1_CLKIN_IBUFG));
BUFG  U1_CLK0_BUFG_INST (.I(U1_CLK0_BUF), 
                       .O(U1_CLK0_OUT));
BUFG  U2_CLKDV_BUFG_INST (.I(U2_CLKDV_BUF), 
                        .O(U2_CLKDV_OUT));
BUFG  U2_CLKFX_BUFG_INST (.I(U2_CLKFX_BUF), 
                        .O(U2_CLKFX_OUT));
BUFG  U2_CLK0_BUFG_INST (.I(U2_CLK0_BUF), 
                       .O(U2_CLKFB_IN));
BUFG  U2_CLK2X_BUFG_INST (.I(U2_CLK2X_BUF), 
                        .O(U2_CLK2X_OUT));
BUFG  U1_CLK_OUT_BUFG_INST (.I(CLKFX_OUT),
                          .O(CLKFX_OUT_IBUFG));

wire U1_FDS_Q_OUT;
wire U1_FD1_Q_OUT;
wire U1_FD2_Q_OUT;
wire U1_FD3_Q_OUT;
wire U1_OR3_O_OUT;

FDS  U1_FDS_INST (.C(U1_CLKIN_IBUFG), 
                .D(GND_BIT), 
                .S(GND_BIT), 
                .Q(U1_FDS_Q_OUT));
FD  U1_FD1_INST (.C(U1_CLKIN_IBUFG), 
               .D(U1_FDS_Q_OUT), 
               .Q(U1_FD1_Q_OUT));
FD  U1_FD2_INST (.C(U1_CLKIN_IBUFG), 
               .D(U1_FD1_Q_OUT), 
               .Q(U1_FD2_Q_OUT));
FD  U1_FD3_INST (.C(U1_CLKIN_IBUFG), 
               .D(U1_FD2_Q_OUT), 
               .Q(U1_FD3_Q_OUT));
INV  U1_INV_INST (.I(U1_LOCKED_INV_IN), 
                .O(U2_LOCKED_INV_RST));
OR2  U1_OR2_INST (.I0(U1_USER_RST_IN), 
                .I1(U1_OR3_O_OUT), 
                .O(U1_RST_IN));
OR3  U1_OR3_INST (.I0(U1_FD3_Q_OUT), 
                .I1(U1_FD2_Q_OUT), 
                .I2(U1_FD1_Q_OUT), 
                .O(U1_OR3_O_OUT));


wire U2_FDS_Q_OUT;
wire U2_FD1_Q_OUT;
wire U2_FD2_Q_OUT;
wire U2_FD3_Q_OUT;
wire U2_OR3_O_OUT;

FDS  U2_FDS_INST (.C(CLKFX_OUT_IBUFG), 
                .D(GND_BIT), 
                .S(GND_BIT), 
                .Q(U2_FDS_Q_OUT));
FD  U2_FD1_INST (.C(CLKFX_OUT_IBUFG), 
               .D(U2_FDS_Q_OUT), 
               .Q(U2_FD1_Q_OUT));
FD  U2_FD2_INST (.C(CLKFX_OUT_IBUFG), 
               .D(U2_FD1_Q_OUT), 
               .Q(U2_FD2_Q_OUT));
FD  U2_FD3_INST (.C(CLKFX_OUT_IBUFG), 
               .D(U2_FD2_Q_OUT), 
               .Q(U2_FD3_Q_OUT));
OR2  U2_OR2_INST (.I0(U2_LOCKED_INV_RST), 
                .I1(U2_OR3_O_OUT), 
                .O(U2_RST_IN));
OR3  U2_OR3_INST (.I0(U2_FD3_Q_OUT), 
                .I1(U2_FD2_Q_OUT), 
                .I2(U2_FD1_Q_OUT), 
                .O(U2_OR3_O_OUT));
endmodule
