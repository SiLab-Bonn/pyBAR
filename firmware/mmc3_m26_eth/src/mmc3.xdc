
create_clock -period 10.000 -name clkin -add [get_ports clkin]
create_clock -period 8.000 -name rgmii_rxc -add [get_ports rgmii_rxc]

set_false_path -from [get_clocks CLK125PLLTX] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks CLK125PLLTX]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks rgmii_rxc]
set_false_path -from [get_clocks rgmii_rxc] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks rgmii_rxc]
set_false_path -from [get_clocks rgmii_rxc] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks CLK16_PLL] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks CLK16_PLL]
set_false_path -from [get_clocks CLK160_PLL] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks CLK160_PLL]
set_false_path -from [get_clocks CLK40_PLL] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks CLK40_PLL]

#NET "Clk100" 				LOC =  "AA3" | IOSTANDARD = "LVCMOS15"; 100MHz
set_property PACKAGE_PIN AA3 [get_ports clkin]
set_property IOSTANDARD LVCMOS15 [get_ports clkin]

set_property PACKAGE_PIN C18 [get_ports RESET_N]
set_property IOSTANDARD LVCMOS25 [get_ports RESET_N]
set_property PULLUP true [get_ports RESET_N]

set_property SLEW FAST [get_ports mdio_phy_mdc]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdc]
set_property PACKAGE_PIN N16 [get_ports mdio_phy_mdc]

set_property SLEW FAST [get_ports mdio_phy_mdio]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdio]
set_property PACKAGE_PIN U16 [get_ports mdio_phy_mdio]

set_property SLEW FAST [get_ports phy_rst_n]
set_property IOSTANDARD LVCMOS25 [get_ports phy_rst_n]
set_property PACKAGE_PIN M20 [get_ports phy_rst_n]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rxc]
set_property PACKAGE_PIN R21 [get_ports rgmii_rxc]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rx_ctl]
set_property PACKAGE_PIN P21 [get_ports rgmii_rx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[0]}]
set_property PACKAGE_PIN P16 [get_ports {rgmii_rxd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[1]}]
set_property PACKAGE_PIN N17 [get_ports {rgmii_rxd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[2]}]
set_property PACKAGE_PIN R16 [get_ports {rgmii_rxd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[3]}]
set_property PACKAGE_PIN R17 [get_ports {rgmii_rxd[3]}]

set_property SLEW FAST [get_ports rgmii_txc]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_txc]
set_property PACKAGE_PIN R18 [get_ports rgmii_txc]

set_property SLEW FAST [get_ports rgmii_tx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_tx_ctl]
set_property PACKAGE_PIN P18 [get_ports rgmii_tx_ctl]

set_property SLEW FAST [get_ports {rgmii_txd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[0]}]
set_property PACKAGE_PIN N18 [get_ports {rgmii_txd[0]}]
set_property SLEW FAST [get_ports {rgmii_txd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[1]}]
set_property PACKAGE_PIN M19 [get_ports {rgmii_txd[1]}]
set_property SLEW FAST [get_ports {rgmii_txd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[2]}]
set_property PACKAGE_PIN U17 [get_ports {rgmii_txd[2]}]
set_property SLEW FAST [get_ports {rgmii_txd[3]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[3]}]
set_property PACKAGE_PIN T17 [get_ports {rgmii_txd[3]}]


set_property PACKAGE_PIN M17 [get_ports {LED[0]}]
set_property PACKAGE_PIN L18 [get_ports {LED[1]}]
set_property PACKAGE_PIN L17 [get_ports {LED[2]}]
set_property PACKAGE_PIN K18 [get_ports {LED[3]}]
set_property PACKAGE_PIN P26 [get_ports {LED[4]}]
set_property PACKAGE_PIN M25 [get_ports {LED[5]}]
set_property PACKAGE_PIN L25 [get_ports {LED[6]}]
set_property PACKAGE_PIN P23 [get_ports {LED[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports LED*]
set_property SLEW SLOW [get_ports LED*]


#PORT 0?
set_property PACKAGE_PIN B9 [get_ports CMD_CLK_N]
set_property PACKAGE_PIN D8 [get_ports CMD_DATA_N]
set_property IOSTANDARD LVDS_25 [get_ports CMD_CLK*]
set_property IOSTANDARD LVDS_25 [get_ports CMD_DATA*]

set_property PACKAGE_PIN H12 [get_ports RJ45_HITOR_P]
set_property PACKAGE_PIN H11 [get_ports RJ45_HITOR_N]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]

set_property PACKAGE_PIN J10 [get_ports DOBOUT_N]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]

set_property KEEPER true [get_ports DOBOUT_P]


set_property BITSTREAM.CONFIG.UNUSEDPIN PULLUP [current_design]


#####
set_property PACKAGE_PIN F9 [get_ports {M26_DATA1_P[0]}]
set_property PACKAGE_PIN F8 [get_ports {M26_DATA1_N[0]}]
set_property PACKAGE_PIN C12 [get_ports {M26_MKD_P[0]}]
set_property PACKAGE_PIN C11 [get_ports {M26_MKD_N[0]}]
set_property PACKAGE_PIN G12 [get_ports {M26_DATA0_P[0]}]
set_property PACKAGE_PIN F12 [get_ports {M26_DATA0_N[0]}]
set_property PACKAGE_PIN C14 [get_ports {M26_CLK_P[0]}]
set_property PACKAGE_PIN C13 [get_ports {M26_CLK_N[0]}]

set_property PACKAGE_PIN B12 [get_ports {M26_DATA1_P[1]}]
set_property PACKAGE_PIN B11 [get_ports {M26_DATA1_N[1]}]
set_property PACKAGE_PIN B15 [get_ports {M26_MKD_P[1]}]
set_property PACKAGE_PIN A15 [get_ports {M26_MKD_N[1]}]
set_property PACKAGE_PIN B17 [get_ports {M26_DATA0_P[1]}]
set_property PACKAGE_PIN A17 [get_ports {M26_DATA0_N[1]}]
set_property PACKAGE_PIN C19 [get_ports {M26_CLK_P[1]}]
set_property PACKAGE_PIN B19 [get_ports {M26_CLK_N[1]}]

set_property PACKAGE_PIN D15 [get_ports {M26_DATA1_P[2]}]
set_property PACKAGE_PIN D16 [get_ports {M26_DATA1_N[2]}]
set_property PACKAGE_PIN H16 [get_ports {M26_MKD_P[2]}]
set_property PACKAGE_PIN G16 [get_ports {M26_MKD_N[2]}]
set_property PACKAGE_PIN G17 [get_ports {M26_DATA0_P[2]}]
set_property PACKAGE_PIN F18 [get_ports {M26_DATA0_N[2]}]
set_property PACKAGE_PIN J15 [get_ports {M26_CLK_P[2]}]
set_property PACKAGE_PIN J16 [get_ports {M26_CLK_N[2]}]

set_property PACKAGE_PIN J13 [get_ports {M26_CLK_P[3]}]
set_property PACKAGE_PIN H13 [get_ports {M26_CLK_N[3]}]
set_property PACKAGE_PIN H14 [get_ports {M26_DATA0_P[3]}]
set_property PACKAGE_PIN G14 [get_ports {M26_DATA0_N[3]}]
set_property PACKAGE_PIN E10 [get_ports {M26_MKD_P[3]}]
set_property PACKAGE_PIN D10 [get_ports {M26_MKD_N[3]}]
set_property PACKAGE_PIN A9 [get_ports {M26_DATA1_P[3]}]
set_property PACKAGE_PIN A8 [get_ports {M26_DATA1_N[3]}]

set_property PACKAGE_PIN H9 [get_ports {M26_CLK_P[4]}]
set_property PACKAGE_PIN H8 [get_ports {M26_CLK_N[4]}]
set_property PACKAGE_PIN F14 [get_ports {M26_DATA0_P[4]}]
set_property PACKAGE_PIN F13 [get_ports {M26_DATA0_N[4]}]
set_property PACKAGE_PIN E11 [get_ports {M26_MKD_P[4]}]
set_property PACKAGE_PIN D11 [get_ports {M26_MKD_N[4]}]
set_property PACKAGE_PIN D14 [get_ports {M26_DATA1_P[4]}]
set_property PACKAGE_PIN D13 [get_ports {M26_DATA1_N[4]}]

set_property PACKAGE_PIN E13 [get_ports {M26_CLK_P[5]}]
set_property PACKAGE_PIN E12 [get_ports {M26_CLK_N[5]}]
set_property PACKAGE_PIN B14 [get_ports {M26_DATA0_P[5]}]
set_property PACKAGE_PIN A14 [get_ports {M26_DATA0_N[5]}]
set_property PACKAGE_PIN B10 [get_ports {M26_MKD_P[5]}]
set_property PACKAGE_PIN A10 [get_ports {M26_MKD_N[5]}]
set_property PACKAGE_PIN C16 [get_ports {M26_DATA1_P[5]}]
set_property PACKAGE_PIN B16 [get_ports {M26_DATA1_N[5]}]

set_property IOSTANDARD LVDS_25 [get_ports M26_*]

#set_property PACKAGE_PIN A19 [get_ports {M26_CLK_N[6]}]
#set_property PACKAGE_PIN C18 [get_ports {M26_MKD_N[6]}]
#set_property PACKAGE_PIN E17 [get_ports {M26_DATA0_N[6]}]
#set_property PACKAGE_PIN E16 [get_ports {M26_DATA1_N[6}]

create_clock -period 12.500 -name m26_clk0 -add [get_ports {M26_CLK_P[0]}]
create_clock -period 12.500 -name m26_clk1 -add [get_ports {M26_CLK_P[1]}]
create_clock -period 12.500 -name m26_clk2 -add [get_ports {M26_CLK_P[2]}]
create_clock -period 12.500 -name m26_clk3 -add [get_ports {M26_CLK_P[3]}]
create_clock -period 12.500 -name m26_clk4 -add [get_ports {M26_CLK_P[4]}]
create_clock -period 12.500 -name m26_clk5 -add [get_ports {M26_CLK_P[5]}]

set_false_path -from [get_clocks m26_clk0] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks m26_clk1] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks m26_clk2] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks m26_clk3] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks m26_clk4] -to [get_clocks BUS_CLK_PLL]
set_false_path -from [get_clocks m26_clk5] -to [get_clocks BUS_CLK_PLL]

set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk0]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk1]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk2]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk3]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk4]
set_false_path -from [get_clocks BUS_CLK_PLL] -to [get_clocks m26_clk5]

## Port 7
set_property PACKAGE_PIN A19 [get_ports M26_TCK_N]
set_property PACKAGE_PIN A18 [get_ports M26_TCK_P]
set_property IOSTANDARD LVDS_25 [get_ports M26_TCK*]

set_property PACKAGE_PIN F17 [get_ports M26_TMS_P]
set_property PACKAGE_PIN E17 [get_ports M26_TMS_N]
set_property IOSTANDARD LVDS_25 [get_ports M26_TMS*]

set_property PACKAGE_PIN E15 [get_ports M26_TDI_P]
set_property PACKAGE_PIN E16 [get_ports M26_TDI_N]
set_property IOSTANDARD LVDS_25 [get_ports M26_TDI*]

set_property PACKAGE_PIN F15 [get_ports M26_TDO_N]
set_property PACKAGE_PIN G15 [get_ports M26_TDO_P]
set_property IOSTANDARD LVDS_25 [get_ports M26_TDO*]


set_property PACKAGE_PIN V23 [get_ports RJ45_BUSY_LEMO_TX1]
set_property PACKAGE_PIN AB21 [get_ports RJ45_CLK_LEMO_TX0]
set_property PACKAGE_PIN V21 [get_ports RJ45_TRIGGER]
set_property PACKAGE_PIN Y25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_BUSY_LEMO_TX1]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_CLK_LEMO_TX0]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_TRIGGER]

set_property PACKAGE_PIN U26 [get_ports {LEMO_RX[1]}]
set_property PACKAGE_PIN U22 [get_ports {LEMO_RX[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_RX*]


#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets p_23_out]

#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[0].IBUFDS_inst_M26_CLK]
#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[1].IBUFDS_inst_M26_CLK]
#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[2].IBUFDS_inst_M26_CLK]
#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[3].IBUFDS_inst_M26_CLK]
#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[4].IBUFDS_inst_M26_CLK]
#set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets n_0_m26_gen[5].IBUFDS_inst_M26_CLK]

set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_0]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_1]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_2]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_3]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_4]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets M26_CLK_5]

