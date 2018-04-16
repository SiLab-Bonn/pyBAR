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

`timescale 1ps / 1ps
`default_nettype none

module top (
    input wire FCLK_IN, // 48MHz

    //full speed
    inout wire [7:0] BUS_DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,

    //high speed
    inout wire [7:0] FDATA,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //debug ports
//    output wire [15:0] DEBUG_D,
    output wire [10:0] MULTI_IO, // Pin 1-11, 12: not connected, 13, 15: DGND, 14, 16: VCC_3.3V

    //LED
    output wire [4:0] LED,

    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,

    input wire [2:0] LEMO_RX,
    output wire [2:0] TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,

    // FE RefClk (SCAC, BIC, GPAC)
    output wire REF_CLK,

    // FE DI (SCAC, BIC, GPAC)
    output wire CMD_DATA,

`ifdef GPAC
    // FE DOBOUT
    input wire DOBOUT,

    // CCPD
    output wire CCPD_SHIFT_LD,
    output wire CCPD_SHIFT_IN,
    input wire CCPD_SHIFT_OUT,
    input wire CCPD_TDC,
    output wire CCPD_GLOBAL_SHIFT_CLK,
    output wire CCPD_CONFIG_SHIFT_CLK,

    //GPAC
    input wire [11:0] DIN,
    output wire [19:0] DOUT,
//    input [3:0] ADC_OUT_P,
//    input [3:0] ADC_OUT_N,
//    output ADC_CLK_N,
//    output ADC_CLK_P,
//    input ADC_FCO_N,
//    input ADC_FCO_P,
//    input ADC_DCO_N,
//    input ADC_DCO_P,
//    output ADC_SDI,
//    output ADC_SCLK,
//    output ADC_CS_B,
//    input ADC_SDO,

    output INJ_STRB,
`else
    // FE AuxClk (SCAC)
    output wire AUX_CLK,

    // FE DOBOUT (SCAC and BIC)
    input wire [3:0] DOBOUT,

    // Voltage Regulator Enable (SCAC and BIC)
    output wire [3:0] EN,

    // Voltage Regulator VPLL Enable (old SCAC)
    output wire EN_VPLL,

    // Over Current Protection (BIC only)
    input wire [3:0] OC, // active low

    // Select (SEL) LED (BIC only)
    output wire [3:0] SEL,

    // other IOs on SCAC
    output wire [2:0] IOMXSEL,
    output wire [3:0] IOMXIN,
    input  wire [2:0] IOMXOUT,

    output wire CMD_ALT_PLS,
    output wire CMD_EXT_TRIGGER,
    output wire SEL_CMD,
    output wire SEL_ALT_BUS,

    output wire REG_AB_DAC_LD,
    output wire REG_AB_STB_LD,
`endif

    // FE Hitbus (SCAC only)
    input wire MONHIT,

    //input wire FPGA_BUTTON // switch S2 on MultiIO board, active low

    // I2C
    inout SDA,
    inout SCL
);

`ifdef GPAC
// assignments for SCC_HVCMOS2FE-I4B_V1.0 and SCC_HVCMOS2FE-I4B_V1.1
// CCPD
wire CCPD_GLOBAL_SHIFT_OUT;
assign CCPD_GLOBAL_SHIFT_OUT = CCPD_SHIFT_OUT;
wire CCPD_CONFIG_SHIFT_OUT;
assign CCPD_CONFIG_SHIFT_OUT = CCPD_SHIFT_OUT;
wire CCPD_CONFIG_SHIFT_IN, CCPD_GLOBAL_SHIFT_IN;
assign CCPD_SHIFT_IN = CCPD_CONFIG_SHIFT_IN | CCPD_GLOBAL_SHIFT_IN;
wire CCPD_CONFIG_SHIFT_LD, CCPD_GLOBAL_SHIFT_LD;
assign CCPD_SHIFT_LD = CCPD_CONFIG_SHIFT_LD | CCPD_GLOBAL_SHIFT_LD;
wire INJECT_PULSE;
assign INJ_STRB = INJECT_PULSE;
//wire ADC_ENC_P;
//assign ADC_CLK_P = ADC_ENC_P;
//wire ADC_ENC_N;
//assign ADC_CLK_N = ADC_ENC_N;
//wire ADC_CSN;
//assign ADC_CS_B = ADC_CSN;
`endif

// Assignments
wire BUS_RST;
(* KEEP = "{TRUE}" *) wire BUS_CLK;
(* KEEP = "{TRUE}" *) wire CLK40;
wire RX_CLK;
wire RX_CLK2X;
wire DATA_CLK;
wire CLK_LOCKED;

// LEMO Rx
wire LEMO_TRIGGER, MULTI_PURPOSE, TDC_IN;
assign LEMO_TRIGGER = LEMO_RX[0];
assign MULTI_PURPOSE = LEMO_RX[1];
assign TDC_IN = LEMO_RX[2];

// TLU
wire TLU_BUSY; // busy signal to TLU to de-assert trigger
wire TLU_CLOCK;

// CMD
wire CMD_EXT_START_FLAG; // to CMD FSM
wire TRIGGER_ACCEPTED_FLAG; // from TLU FSM
`ifdef GPAC
wire INJ_CMD_EXT_START_FLAG;
assign CMD_EXT_START_FLAG = TRIGGER_ACCEPTED_FLAG | INJ_CMD_EXT_START_FLAG;
`else
assign CMD_EXT_START_FLAG = TRIGGER_ACCEPTED_FLAG;
`endif
wire EXT_TRIGGER_ENABLE; // from CMD FSM
wire CMD_READY; // from CMD FSM
wire TRIGGER_ACKNOWLEDGE_FLAG; // to TLU FSM

reg CMD_READY_FF;
always @ (posedge CLK40)
begin
    CMD_READY_FF <= CMD_READY;
end
assign TRIGGER_ACKNOWLEDGE_FLAG = CMD_READY & ~CMD_READY_FF;

wire CMD_START_FLAG; // sending FE command triggered by external devices
//reg CMD_CAL; // when CAL command is send
wire TRIGGER_ENABLED, TLU_ENABLED;

// LEMO Tx
assign TX[0] = TLU_CLOCK;
assign TX[1] = TLU_BUSY;
assign TX[2] = RJ45_TRIGGER;

// ------- RESRT/CLOCK  ------- //
reset_gen ireset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

`ifdef SLOW_CLK
assign RX_CLK = CLK40; // 12MHz

clk_gen_12mhz iclkgen(
    .U1_CLKIN_IN(FCLK_IN),
    .U1_USER_RST_IN(1'b0),
    .U1_CLKIN_IBUFG_OUT(),
    .U1_CLK0_OUT(BUS_CLK), // DCM1: 48MHz USB/SRAM clock
    .U1_STATUS_OUT(),
    .U2_CLKFX_OUT(CLK40), // DCM2: 40MHz command clock
    .U2_CLKDV_OUT(DATA_CLK), // DCM2: 16MHz SERDES clock
    .U2_CLK0_OUT(),
    .U2_CLK2X_OUT(RX_CLK2X), // DCM2: 24MHz data recovery clock
    .U2_LOCKED_OUT(CLK_LOCKED),
    .U2_STATUS_OUT()
);
`else
clk_gen iclkgen(
    .U1_CLKIN_IN(FCLK_IN),
    .U1_USER_RST_IN(1'b0),
    .U1_CLKIN_IBUFG_OUT(),
    .U1_CLK0_OUT(BUS_CLK), // DCM1: 48MHz USB/SRAM clock
    .U1_STATUS_OUT(),
    .U2_CLKFX_OUT(CLK40), // DCM2: 40MHz command clock
    .U2_CLKDV_OUT(DATA_CLK), // DCM2: 16MHz SERDES clock
    .U2_CLK0_OUT(RX_CLK), // DCM2: 160MHz data clock
    .U2_CLK2X_OUT(RX_CLK2X), // DCM2: 320MHz data recovery clock
    .U2_LOCKED_OUT(CLK_LOCKED),
    .U2_STATUS_OUT()
);
`endif

`ifndef GPAC
wire CE_10MHZ;
wire CLK_10MHZ;
clock_divider #(
    .DIVISOR(4)
) i_clock_divisor_40MHz_to_10MHz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(CE_10MHZ),
    .CLOCK(CLK_10MHZ)
);

assign AUX_CLK = CLK_10MHZ;
/*
ODDR AUX_CLK_FORWARDING_INST (
    .Q(AUX_CLK),
    .C(CLK40),
    .CE(CE_10MHZ),
    .D1(1'b1),
    .D2(1'b0),
    .R(1'b0),
    .S(1'b0)
);
*/

assign IOMXSEL  = 0;
assign IOMXIN = 0;
assign CMD_ALT_PLS = 0;
assign CMD_EXT_TRIGGER = 0;
assign SEL_CMD = 1; // hold this pin high
assign SEL_ALT_BUS = 0;
assign REG_AB_DAC_LD = 0;
assign REG_AB_STB_LD = 0;
`endif

// 1Hz CLK
wire CE_1HZ; // use for sequential logic
wire CLK_1HZ; // don't connect to clock input, only combinatorial logic
clock_divider #(
`ifdef SLOW_CLK
    .DIVISOR(12000000)
`else
    .DIVISOR(40000000)
`endif
) i_clock_divisor_40MHz_to_1Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(CE_1HZ),
    .CLOCK(CLK_1HZ)
);

wire CLK_3HZ;
clock_divider #(
`ifdef SLOW_CLK
    .DIVISOR(4000000)
`else
    .DIVISOR(13333333)
`endif
) i_clock_divisor_40MHz_to_3Hz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(),
    .CLOCK(CLK_3HZ)
);

// -------  MODULE ADDRESSES  ------- //
localparam CMD_BASEADDR = 16'h0000;
localparam CMD_HIGHADDR = 16'h8000-1;

localparam FIFO_BASEADDR = 16'h8100;
localparam FIFO_HIGHADDR = 16'h8200-1;

localparam TLU_BASEADDR = 16'h8200;
localparam TLU_HIGHADDR = 16'h8300-1;

localparam RX4_BASEADDR = 16'h8300;
localparam RX4_HIGHADDR = 16'h8400-1;

`ifndef GPAC
localparam RX3_BASEADDR = 16'h8400;
localparam RX3_HIGHADDR = 16'h8500-1;

localparam RX2_BASEADDR = 16'h8500;
localparam RX2_HIGHADDR = 16'h8600-1;

localparam RX1_BASEADDR = 16'h8600;
localparam RX1_HIGHADDR = 16'h8700-1;
`endif

localparam TDC_BASEADDR = 16'h8700;
localparam TDC_HIGHADDR = 16'h8800-1;

localparam GPIO_RX_BASEADDR = 16'h8800;
localparam GPIO_RX_HIGHADDR = 16'h8900-1;

`ifdef GPAC
// CCPD

localparam GPAC_ADC_SPI_BASEADDR = 16'h8900;
localparam GPAC_ADC_SPI_HIGHADDR = 16'h893f;

localparam GPAC_ADC_RX_BASEADDR = 16'h8940;
localparam GPAC_ADC_RX_HIGHADDR = 16'h894f;

localparam GPAC_ADC_RX_BASEADDR_1 = 16'h8950;
localparam GPAC_ADC_RX_HIGHADDR_1 = 16'h895f;

localparam CCPD_GLOBAL_SPI_BASEADDR = 16'h8980;
localparam CCPD_GLOBAL_SPI_HIGHADDR = 16'h89ff;

localparam CCPD_PULSE_TDCGATE_BASEADDR = 16'h8A00;
localparam CCPD_PULSE_TDCGATE_HIGHADDR = 16'h8A7f;

localparam CCPD_PULSE_INJ_BASEADDR = 16'h8A80;
localparam CCPD_PULSE_INJ_HIGHADDR = 16'h8Aff;

localparam CCPD_CONFIG_SPI_BASEADDR = 16'h9000;
localparam CCPD_CONFIG_SPI_HIGHADDR = 16'h907f;

localparam CCPD_TDC_BASEADDR = 16'h9100;
localparam CCPD_TDC_HIGHADDR = 16'h91ff;
`else
localparam GPIO_POWER_BASEADDR = 16'h8900;
localparam GPIO_POWER_HIGHADDR = 16'h8A00-1;
`endif

// -------  BUS SIGNALLING  ------- //
wire [15:0] BUS_ADD;
wire BUS_RD, BUS_WR;
// BASIL bus mapping
fx2_to_bus i_fx2_to_bus (
    .ADD(ADD),
    .RD_B(RD_B),
    .WR_B(WR_B),

    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .CS_FPGA()
);

// -------  USER MODULES  ------- //
wire FIFO_NOT_EMPTY; // raised, when SRAM FIFO is not empty
wire FIFO_FULL, FIFO_NEAR_FULL; // raised, when SRAM FIFO is full / near full
wire FIFO_READ_ERROR; // raised, when attempting to read from SRAM FIFO when it is empty

cmd_seq #(
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR)
) icmd (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .CMD_CLK_OUT(REF_CLK),
    .CMD_CLK_IN(CLK40),
    .CMD_EXT_START_FLAG(CMD_EXT_START_FLAG),
    .CMD_EXT_START_ENABLE(EXT_TRIGGER_ENABLE),
    .CMD_DATA(CMD_DATA),
    .CMD_READY(CMD_READY),
    .CMD_START_FLAG(CMD_START_FLAG)
);

//Recognize CAL command for external device triggering
//reg [8:0] cmd_rx_reg;
//always@(posedge REF_CLK)
//    cmd_rx_reg[8:0] <= {cmd_rx_reg[7:0],CMD_DATA};
//
//always@(posedge REF_CLK)
//    CMD_CAL <= (cmd_rx_reg == 9'b101100100);

parameter DSIZE = 10;
//parameter CLKIN_PERIOD = 6.250;

`ifdef GPAC
wire RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL;
wire RX_ENABLED, RX_ENABLED_CLK40;
three_stage_synchronizer three_stage_sync_rx_enable_clk40 (
    .CLK(CLK40),
    .IN(RX_ENABLED),
    .OUT(RX_ENABLED_CLK40)
);
wire FE_FIFO_EMPTY, FE_FIFO_EMPTY_CLK40;
three_stage_synchronizer three_stage_sync_fe_fifo_empty_clk40 (
    .CLK(CLK40),
    .IN(FE_FIFO_EMPTY),
    .OUT(FE_FIFO_EMPTY_CLK40)
);
wire [31:0] FE_FIFO_DATA;
wire FE_FIFO_READ;

fei4_rx #(
    .BASEADDR(RX4_BASEADDR),
    .HIGHADDR(RX4_HIGHADDR),
    .DSIZE(DSIZE),
    .DATA_IDENTIFIER(4)
) i_fei4_rx (
    .RX_CLK(RX_CLK),
    .RX_CLK2X(RX_CLK2X),
    .DATA_CLK(DATA_CLK),

    .RX_DATA(DOBOUT),

    .RX_READY(RX_READY),
    .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR),
    .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR),

    .FIFO_CLK(1'b0),
    .FIFO_READ(FE_FIFO_READ),
    .FIFO_EMPTY(FE_FIFO_EMPTY),
    .FIFO_DATA(FE_FIFO_DATA),

    .RX_FIFO_FULL(RX_FIFO_FULL),
    .RX_ENABLED(RX_ENABLED),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR)
);
`else
wire [3:0] RX_READY, RX_8B10B_DECODER_ERR, RX_FIFO_OVERFLOW_ERR, RX_FIFO_FULL;
wire [3:0] RX_ENABLED, RX_ENABLED_CLK40;
three_stage_synchronizer #(
    .WIDTH(4)
) three_stage_sync_rx_enable_clk40 (
    .CLK(CLK40),
    .IN(RX_ENABLED),
    .OUT(RX_ENABLED_CLK40)
);
wire [3:0] FE_FIFO_EMPTY, FE_FIFO_EMPTY_CLK40;
three_stage_synchronizer #(
    .WIDTH(4)
) three_stage_sync_fe_fifo_empty_clk40 (
    .CLK(CLK40),
    .IN(FE_FIFO_EMPTY),
    .OUT(FE_FIFO_EMPTY_CLK40)
);
wire [31:0] FE_FIFO_DATA [3:0];
wire [3:0] FE_FIFO_READ;

genvar i;
generate
for (i = 0; i < 4; i = i + 1) begin: rx_gen
    fei4_rx #(
        .BASEADDR(RX1_BASEADDR-16'h0100*i),
        .HIGHADDR(RX1_HIGHADDR-16'h0100*i),
        .DSIZE(DSIZE),
        .DATA_IDENTIFIER(i+1)
    ) i_fei4_rx (
        .RX_CLK(RX_CLK),
        .RX_CLK2X(RX_CLK2X),
        .DATA_CLK(DATA_CLK),

        .RX_DATA(DOBOUT[i]),

        .RX_READY(RX_READY[i]),
        .RX_8B10B_DECODER_ERR(RX_8B10B_DECODER_ERR[i]),
        .RX_FIFO_OVERFLOW_ERR(RX_FIFO_OVERFLOW_ERR[i]),

        .FIFO_CLK(1'b0),
        .FIFO_READ(FE_FIFO_READ[i]),
        .FIFO_EMPTY(FE_FIFO_EMPTY[i]),
        .FIFO_DATA(FE_FIFO_DATA[i]),

        .RX_FIFO_FULL(RX_FIFO_FULL[i]),
        .RX_ENABLED(RX_ENABLED[i]),

        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
    );
end
endgenerate
`endif

wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;
wire [31:0] TIMESTAMP;
wire LEMO_TRIGGER_FROM_TDC;
wire TDC_IN_FROM_TDC;

tdc_s3 #(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100),
    .FAST_TDC(1),
    .FAST_TRIGGER(1)
) i_tdc (
    .CLK320(RX_CLK2X),
    .CLK160(RX_CLK),
    .DV_CLK(CLK40),
    .TDC_IN(TDC_IN),
    .TDC_OUT(TDC_IN_FROM_TDC),
    .TRIG_IN(LEMO_TRIGGER),
    .TRIG_OUT(LEMO_TRIGGER_FROM_TDC),

    .FIFO_READ(TDC_FIFO_READ),
    .FIFO_EMPTY(TDC_FIFO_EMPTY),
    .FIFO_DATA(TDC_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(CMD_START_FLAG), // arm TDC by sending commands
    .EXT_EN(1'b0),

    .TIMESTAMP(TIMESTAMP[15:0])
);

`ifdef GPAC
wire [3:0] NOT_CONNECTED_RX;
wire SEL, TLU_SEL, TDC_SEL, CCPD_TDC_SEL;
gpio #(
    .BASEADDR(GPIO_RX_BASEADDR),
    .HIGHADDR(GPIO_RX_HIGHADDR),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff),
    .IO_TRI(8'h00),
    .ABUSWIDTH(16)
) i_gpio_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_RX, CCPD_TDC_SEL, TDC_SEL, TLU_SEL, SEL})
);

parameter max_wait_cycles = 64;
reg STARTED_READY_COUNTER;
reg CMD_FIFO_READY;
integer fifo_empty_counter;
wire CMD_FIFO_READY_FLAG;
reg CMD_FIFO_READY_FF;

always @(posedge CLK40)
begin
    STARTED_READY_COUNTER <= STARTED_READY_COUNTER;
    CMD_FIFO_READY <= CMD_FIFO_READY;
    fifo_empty_counter <= fifo_empty_counter;

    if (~EXT_TRIGGER_ENABLE || ~TRIGGER_ENABLED)
    begin
        STARTED_READY_COUNTER <= 1'b0;
        CMD_FIFO_READY <= 1'b1;
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b0 && TRIGGER_ACKNOWLEDGE_FLAG == 1'b1)
    begin
        STARTED_READY_COUNTER <= 1'b1;
        CMD_FIFO_READY <= 1'b0;
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && |(~FE_FIFO_EMPTY_CLK40 & RX_ENABLED_CLK40))
    begin
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && fifo_empty_counter == max_wait_cycles)
    begin
        STARTED_READY_COUNTER <= 1'b0;
        CMD_FIFO_READY <= 1'b1;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && &(FE_FIFO_EMPTY_CLK40 | ~RX_ENABLED_CLK40))
    begin
        fifo_empty_counter <= fifo_empty_counter + 1;
    end
end

always @ (posedge CLK40)
begin
    CMD_FIFO_READY_FF <= CMD_FIFO_READY;
end
assign CMD_FIFO_READY_FLAG = CMD_FIFO_READY & ~CMD_FIFO_READY_FF;

wire TRIGGER_FIFO_READ;
wire TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA;
wire TRIGGER_FIFO_PEEMPT_REQ;
wire CCPD_TDC_FROM_TDC;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(32),
    .WIDTH(8),
    .TLU_TRIGGER_MAX_CLOCK_CYCLES(32)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TRIGGER_CLK(CLK40),

    .FIFO_READ(TRIGGER_FIFO_READ),
    .FIFO_EMPTY(TRIGGER_FIFO_EMPTY),
    .FIFO_DATA(TRIGGER_FIFO_DATA),

    .FIFO_PREEMPT_REQ(TRIGGER_FIFO_PEEMPT_REQ),

    .TRIGGER_ENABLED(TRIGGER_ENABLED),
    .TRIGGER_SELECTED(),
    .TLU_ENABLED(TLU_ENABLED),

    .TRIGGER({3'b0, CCPD_TDC_FROM_TDC, TDC_IN_FROM_TDC, MULTI_PURPOSE, LEMO_TRIGGER_FROM_TDC, MONHIT}),
    .TRIGGER_VETO({6'b0, MULTI_PURPOSE, FIFO_FULL}),
    .TIMESTAMP_RESET(1'b0),

    .EXT_TRIGGER_ENABLE(EXT_TRIGGER_ENABLE),
    .TRIGGER_ACKNOWLEDGE(CMD_FIFO_READY_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),

    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),

    .TIMESTAMP(TIMESTAMP)
);
`else
wire [1:0] NOT_CONNECTED_RX;
wire TLU_SEL, TDC_SEL;
gpio #(
    .BASEADDR(GPIO_RX_BASEADDR),
    .HIGHADDR(GPIO_RX_HIGHADDR),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'hff)
) i_gpio_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO({NOT_CONNECTED_RX, TDC_SEL, TLU_SEL, SEL[3], SEL[2], SEL[1], SEL[0]})
);

wire [7:0] GPIO_POWER_IO;
assign EN = GPIO_POWER_IO[3:0];
assign EN_VPLL = GPIO_POWER_IO[2]; // EN_VD2
assign GPIO_POWER_IO[7:4] = ~{OC[3], OC[2], OC[1], OC[0]};
gpio #(
    .BASEADDR(GPIO_POWER_BASEADDR),
    .HIGHADDR(GPIO_POWER_HIGHADDR),
    .IO_WIDTH(8),
    .IO_DIRECTION(8'h0f)
) i_gpio_power (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(GPIO_POWER_IO)
);

parameter max_wait_cycles = 64;
reg STARTED_READY_COUNTER;
reg CMD_FIFO_READY;
integer fifo_empty_counter;
wire CMD_FIFO_READY_FLAG;
reg CMD_FIFO_READY_FF;

always @(posedge CLK40)
begin
    STARTED_READY_COUNTER <= STARTED_READY_COUNTER;
    CMD_FIFO_READY <= CMD_FIFO_READY;
    fifo_empty_counter <= fifo_empty_counter;

    if (~EXT_TRIGGER_ENABLE || ~TRIGGER_ENABLED)
    begin
        STARTED_READY_COUNTER <= 1'b0;
        CMD_FIFO_READY <= 1'b1;
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b0 && TRIGGER_ACKNOWLEDGE_FLAG == 1'b1)
    begin
        STARTED_READY_COUNTER <= 1'b1;
        CMD_FIFO_READY <= 1'b0;
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && |(~FE_FIFO_EMPTY_CLK40 & RX_ENABLED_CLK40))
    begin
        fifo_empty_counter <= 0;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && fifo_empty_counter == max_wait_cycles)
    begin
        STARTED_READY_COUNTER <= 1'b0;
        CMD_FIFO_READY <= 1'b1;
    end
    else if (STARTED_READY_COUNTER == 1'b1 && &(FE_FIFO_EMPTY_CLK40 | ~RX_ENABLED_CLK40))
    begin
        fifo_empty_counter <= fifo_empty_counter + 1;
    end
end

always @ (posedge CLK40)
begin
    CMD_FIFO_READY_FF <= CMD_FIFO_READY;
end
assign CMD_FIFO_READY_FLAG = CMD_FIFO_READY & ~CMD_FIFO_READY_FF;

wire TRIGGER_FIFO_READ;
wire TRIGGER_FIFO_EMPTY;
wire [31:0] TRIGGER_FIFO_DATA;
wire TRIGGER_FIFO_PEEMPT_REQ;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(32),
    .TLU_TRIGGER_MAX_CLOCK_CYCLES(32)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TRIGGER_CLK(CLK40),

    .FIFO_READ(TRIGGER_FIFO_READ),
    .FIFO_EMPTY(TRIGGER_FIFO_EMPTY),
    .FIFO_DATA(TRIGGER_FIFO_DATA),

    .FIFO_PREEMPT_REQ(TRIGGER_FIFO_PEEMPT_REQ),

    .TRIGGER_ENABLED(TRIGGER_ENABLED),
    .TRIGGER_SELECTED(),
    .TLU_ENABLED(TLU_ENABLED),

    .TRIGGER({4'b0, TDC_IN_FROM_TDC, MULTI_PURPOSE, LEMO_TRIGGER_FROM_TDC, MONHIT}),
    .TRIGGER_VETO({6'b0, MULTI_PURPOSE, FIFO_FULL}),
    .TIMESTAMP_RESET(1'b0),

    .EXT_TRIGGER_ENABLE(EXT_TRIGGER_ENABLE),
    .TRIGGER_ACKNOWLEDGE(CMD_FIFO_READY_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),

    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),

    .TIMESTAMP(TIMESTAMP)
);
`endif

`ifdef GPAC
// CCPD
wire SPI_CLK, SPI_CLK_CE;

reg [15:0] INJ_CNT;
wire CCPD_TDC_FIFO_READ;
wire CCPD_TDC_FIFO_EMPTY;
wire [31:0] CCPD_TDC_FIFO_DATA;
wire CCPD_TDCGATE;

tdc_s3 #(
    .BASEADDR(CCPD_TDC_BASEADDR),
    .HIGHADDR(CCPD_TDC_HIGHADDR),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0010),
    .FAST_TDC(1),
    .FAST_TRIGGER(0)
) i_ccpd_tdc (
    .CLK320(RX_CLK2X),
    .CLK160(RX_CLK),
    .DV_CLK(CLK40),
    .TDC_IN(CCPD_TDC),
    .TDC_OUT(CCPD_TDC_FROM_TDC),
    .TRIG_IN(1'b0),
    .TRIG_OUT(),

    .FIFO_READ(CCPD_TDC_FIFO_READ),
    .FIFO_EMPTY(CCPD_TDC_FIFO_EMPTY),
    .FIFO_DATA(CCPD_TDC_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(CMD_START_FLAG), // arm TDC by sending commands

    .TIMESTAMP(INJ_CNT),
    //.TIMESTAMP(TIMESTAMP[15:0]),
    .EXT_EN(CCPD_TDCGATE)
);

/*
wire ADC_EN;
wire ADC_ENC;
clock_divider #(
    .DIVISOR(16) // 10MHz
) i_clock_divisor_40MHz_to_2500kHz (
    .CLK(RX_CLK),
    .RESET(1'b0),
    .CE(),
    .CLOCK(ADC_ENC)
);

spi #(
    .BASEADDR(GPAC_ADC_SPI_BASEADDR),
    .HIGHADDR(GPAC_ADC_SPI_HIGHADDR),
    .MEM_BYTES(2)
) i_spi_gpac_adc (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SPI_CLK(SPI_CLK),

    .SCLK(ADC_SCLK),
    .SDI(ADC_SDI),
    .SDO(ADC_SDO),

    .EXT_START(),
    .SEN(ADC_EN),
    .SLD()
);

assign ADC_CSN = !ADC_EN;
wire [13:0] ADC_IN0, ADC_IN1, ADC_IN2, ADC_IN3;
wire ADC_DCO, ADC_FCO;

gpac_adc_iobuf i_gpac_adc_iobuf (
    .ADC_CLK(RX_CLK),

    .ADC_DCO_P(ADC_DCO_P),
    .ADC_DCO_N(ADC_DCO_N),
    .ADC_DCO(ADC_DCO),

    .ADC_FCO_P(ADC_FCO_P),
    .ADC_FCO_N(ADC_FCO_N),
    .ADC_FCO(ADC_FCO),

    .ADC_ENC(ADC_ENC),
    .ADC_ENC_P(ADC_ENC_P),
    .ADC_ENC_N(ADC_ENC_N),

    .ADC_IN_P(ADC_OUT_P),
    .ADC_IN_N(ADC_OUT_N),

    .ADC_IN0(ADC_IN0),
    .ADC_IN1(ADC_IN1),
    .ADC_IN2(ADC_IN2),
    .ADC_IN3(ADC_IN3)
);

wire FIFO_READ_ADC, FIFO_EMPTY_ADC;
wire [31:0] FIFO_DATA_ADC;
wire ADC_ERROR;

gpac_adc_rx #(
    .BASEADDR(GPAC_ADC_RX_BASEADDR),
    .HIGHADDR(GPAC_ADC_RX_HIGHADDR),
    .ADC_ID(0),
    .HEADER_ID(6)
) i_gpac_adc_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ADC_ENC(ADC_ENC),
    .ADC_IN(ADC_IN0),

    .ADC_SYNC(1'b0),
    .ADC_TRIGGER(1'b0),

    .FIFO_READ(1'b0),
    .FIFO_EMPTY(FIFO_EMPTY_ADC),
    .FIFO_DATA(FIFO_DATA_ADC),

    .LOST_ERROR(ADC_ERROR)
);

wire FIFO_READ_ADC_1, FIFO_EMPTY_ADC_1;
wire [31:0] FIFO_DATA_ADC_1;
wire ADC_ERROR_1;

gpac_adc_rx #(
    .BASEADDR(GPAC_ADC_RX_BASEADDR_1),
    .HIGHADDR(GPAC_ADC_RX_HIGHADDR_1),
    .ADC_ID(1),
    .HEADER_ID(7)
) i_gpac_adc_rx_1 (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ADC_ENC(ADC_ENC),
    .ADC_IN(ADC_IN1),

    .ADC_SYNC(1'b0),
    .ADC_TRIGGER(1'b0),

    .FIFO_READ(1'b0),
    .FIFO_EMPTY(FIFO_EMPTY_ADC_1),
    .FIFO_DATA(FIFO_DATA_ADC_1),

    .LOST_ERROR(ADC_ERROR_1)
);
*/
clock_divider #(
    .DIVISOR(40) // 1MHz
) i_clock_divisor_40MHz_to_1kHz (
    .CLK(CLK40),
    .RESET(1'b0),
    .CE(SPI_CLK_CE),
    .CLOCK(SPI_CLK)
);

spi #(
    .BASEADDR(CCPD_GLOBAL_SPI_BASEADDR),
    .HIGHADDR(CCPD_GLOBAL_SPI_HIGHADDR),
    .MEM_BYTES(17)
) i_ccpd_global_spi_pixel (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SPI_CLK(SPI_CLK),

    .SCLK(CCPD_GLOBAL_SHIFT_CLK),
    .SDI(CCPD_GLOBAL_SHIFT_IN),
    .SDO(CCPD_GLOBAL_SHIFT_OUT),

    .EXT_START(),
    .SEN(),
    .SLD(CCPD_GLOBAL_SHIFT_LD)
);

spi #(
    .BASEADDR(CCPD_CONFIG_SPI_BASEADDR),
    .HIGHADDR(CCPD_CONFIG_SPI_HIGHADDR),
    .MEM_BYTES(54)
) i_ccpd_config_spi_pixel (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SPI_CLK(SPI_CLK),

    .SCLK(CCPD_CONFIG_SHIFT_CLK),
    .SDI(CCPD_CONFIG_SHIFT_IN),
    .SDO(CCPD_CONFIG_SHIFT_OUT),

    .EXT_START(),
    .SEN(),
    .SLD(CCPD_CONFIG_SHIFT_LD)
);

pulse_gen #(
    .BASEADDR(CCPD_PULSE_INJ_BASEADDR),
    .HIGHADDR(CCPD_PULSE_INJ_HIGHADDR)
) i_pulse_gen_inj (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(SPI_CLK),
    .EXT_START(CCPD_TDCGATE),
    .PULSE(INJECT_PULSE)
);

// inject pulse flag
wire INJECT_FLAG;
reg INJECT_PULSE_FF;
always @ (posedge CLK40)
begin
    if (SPI_CLK_CE)
    begin
        INJECT_PULSE_FF <= INJECT_PULSE;
    end
end
assign INJECT_FLAG = INJECT_PULSE & ~INJECT_PULSE_FF;

flag_domain_crossing_ce inject_flag_domain_crossing (
    .CLK_A(CLK40),
    .CLK_A_CE(SPI_CLK_CE),
    .CLK_B(CLK40),
    .CLK_B_CE(1'b1),
    .FLAG_IN_CLK_A(INJECT_FLAG),
    .FLAG_OUT_CLK_B(INJ_CMD_EXT_START_FLAG)
);

pulse_gen #(
    .BASEADDR(CCPD_PULSE_TDCGATE_BASEADDR),
    .HIGHADDR(CCPD_PULSE_TDCGATE_HIGHADDR)
) i_pulse_gen_tdcgate (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(SPI_CLK),
    .EXT_START(1'b0),
    .PULSE(CCPD_TDCGATE)
);

// counter for tdc //
always@(posedge SPI_CLK) begin
    if(BUS_ADD==16'hff00 && BUS_WR)
        INJ_CNT <= 0;
    else if(CCPD_TDCGATE)
        INJ_CNT <= INJ_CNT + 1;
end

// Arbiter
wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [3:0] READ_GRANT;

rrp_arbiter #(
    .WIDTH(4)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~CCPD_TDC_FIFO_EMPTY & CCPD_TDC_SEL, ~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY & TDC_SEL, ~TRIGGER_FIFO_EMPTY & TLU_SEL}),
    .HOLD_REQ({3'b0, TRIGGER_FIFO_PEEMPT_REQ}),
    .DATA_IN({CCPD_TDC_FIFO_DATA, FE_FIFO_DATA, TDC_FIFO_DATA, TRIGGER_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TRIGGER_FIFO_READ = READ_GRANT[0];
assign TDC_FIFO_READ = READ_GRANT[1];
assign FE_FIFO_READ = READ_GRANT[2];
assign CCPD_TDC_FIFO_READ = READ_GRANT[3];
`else
// Arbiter
wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire [5:0] READ_GRANT;

rrp_arbiter #(
    .WIDTH(6)
) i_rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY & TDC_SEL, ~TRIGGER_FIFO_EMPTY & TLU_SEL}),
    .HOLD_REQ({5'b0, TRIGGER_FIFO_PEEMPT_REQ}),
    .DATA_IN({FE_FIFO_DATA[3], FE_FIFO_DATA[2], FE_FIFO_DATA[1], FE_FIFO_DATA[0], TDC_FIFO_DATA, TRIGGER_FIFO_DATA}),
    .READ_GRANT(READ_GRANT),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

assign TRIGGER_FIFO_READ = READ_GRANT[0];
assign TDC_FIFO_READ = READ_GRANT[1];
assign FE_FIFO_READ = READ_GRANT[5:2];

// simple arbiter
//wire ARB_READY_OUT, ARB_WRITE_OUT;
//wire [31:0] ARB_DATA_OUT;
//
//wire [4:0] FIFO_REQ;
//assign FIFO_REQ = TRIGGER_FIFO_PEEMPT_REQ? 5'b0_0000 : {~FE_FIFO_EMPTY & SEL, ~TDC_FIFO_EMPTY & TDC_SEL};
//wire [5:0] FIFO_READ_SEL;
//
//assign {FE_FIFO_READ, TDC_FIFO_READ, TRIGGER_FIFO_READ} = (FIFO_READ_SEL & ({6{ARB_READY_OUT}}));
//assign ARB_WRITE_OUT = ((FIFO_READ_SEL & {FIFO_REQ, ~TRIGGER_FIFO_EMPTY}) != 6'b00_0000);
//assign ARB_DATA_OUT = (({32{FIFO_READ_SEL[5]}} & FE_FIFO_DATA[3]) | ({32{FIFO_READ_SEL[4]}} & FE_FIFO_DATA[2]) | ({32{FIFO_READ_SEL[3]}} & FE_FIFO_DATA[1]) | ({32{FIFO_READ_SEL[2]}} & FE_FIFO_DATA[0]) | ({32{FIFO_READ_SEL[1]}} & TDC_FIFO_DATA) | ({32{FIFO_READ_SEL[0]}} & TRIGGER_FIFO_DATA));
//
//arbiter #(
//    .WIDTH(6)
//) arbiter_inst (
//    .req({FIFO_REQ, ~TRIGGER_FIFO_EMPTY & TLU_SEL}),
//    .grant(FIFO_READ_SEL),
//    .base(6'b00_0001) // one hot, TLU has highest priority followed by higher indexed requests
//);
`endif

// SRAM
wire USB_READ;
assign USB_READ = FREAD & FSTROBE;

sram_fifo #(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR)
) i_out_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),

    .USB_READ(USB_READ),
    .USB_DATA(FDATA),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),

    .FIFO_NOT_EMPTY(FIFO_NOT_EMPTY),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL),
    .FIFO_READ_ERROR(FIFO_READ_ERROR)
);

// ------- LEDs  ------- //

// LED assignments
`ifdef GPAC
assign LED[0] = 1'b0;
assign LED[1] = 1'b0;
assign LED[2] = 1'b0;
assign LED[3] = RX_READY & ((RX_8B10B_DECODER_ERR? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR | RX_FIFO_FULL);
`else
assign LED[0] = RX_READY[0] & ((RX_8B10B_DECODER_ERR[0]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[0] | RX_FIFO_FULL[0]);
assign LED[1] = RX_READY[1] & ((RX_8B10B_DECODER_ERR[1]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[1] | RX_FIFO_FULL[1]);
assign LED[2] = RX_READY[2] & ((RX_8B10B_DECODER_ERR[2]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[2] | RX_FIFO_FULL[2]);
assign LED[3] = RX_READY[3] & ((RX_8B10B_DECODER_ERR[3]? CLK_3HZ : CLK_1HZ) | RX_FIFO_OVERFLOW_ERR[3] | RX_FIFO_FULL[3]);
`endif
assign LED[4] = (CLK_1HZ | FIFO_FULL) & CLK_LOCKED;


// Deubug
assign MULTI_IO = {TDC_IN_FROM_TDC, 10'b00_0000_0000};
//assign DEBUG_D = 16'ha5a5;

// Chipscope
`ifdef SYNTHESIS_NOT
//`ifdef SYNTHESIS
wire [35:0] control_bus;
chipscope_icon ichipscope_icon
(
    .CONTROL0(control_bus)
);

chipscope_ila ichipscope_ila
(
    .CONTROL(control_bus),
    .CLK(CLK_160),
    .TRIG0({FIFO_DATA[23:0], TLU_BUSY, TRIGGER_FIFO_EMPTY, TRIGGER_FIFO_READ, FE_FIFO_EMPTY, FE_FIFO_READ, FIFO_EMPTY, FIFO_READ})
    //.CLK(CLK_160),
    //.TRIG0({FMODE, FSTROBE, FREAD, CMD_BUS_WR, RX_BUS_WR, FIFO_WR, BUS_DATA_IN, DOBOUT4 ,WR_B, RD_B})
);
`endif


endmodule
