
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

#NET "Clk100"   LOC =  "AA3" | IOSTANDARD = "LVCMOS15"; 100MHz
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


#PORT CMD
set_property PACKAGE_PIN B9 [get_ports CMD_DATA_N]
set_property PACKAGE_PIN D8 [get_ports CMD_CLK_N]
set_property IOSTANDARD LVDS_25 [get_ports CMD_CLK*]
set_property IOSTANDARD LVDS_25 [get_ports CMD_DATA*]

set_property BITSTREAM.CONFIG.UNUSEDPIN PULLUP [current_design]

#####################################################

#FANGS
#PORT0
#set_property PACKAGE_PIN B9 [get_ports CMD_DATA_N]
#set_property PACKAGE_PIN D8 [get_ports CMD_CLK_N]
#set_property IOSTANDARD LVDS_25 [get_ports CMD_CLK*]
#set_property IOSTANDARD LVDS_25 [get_ports CMD_DATA*]
set_property PACKAGE_PIN J11 [get_ports RJ45_HITOR_P[1]]
set_property PACKAGE_PIN J10 [get_ports RJ45_HITOR_N[1]]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]

#PORT1
set_property PACKAGE_PIN C14 [get_ports RJ45_HITOR_P[0]]
set_property PACKAGE_PIN C13 [get_ports RJ45_HITOR_N[0]]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]
set_property PACKAGE_PIN G12 [get_ports RJ45_HITOR_P[2]]
set_property PACKAGE_PIN F12 [get_ports RJ45_HITOR_N[2]]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]
set_property PACKAGE_PIN F9 [get_ports RJ45_HITOR_P[3]]
set_property PACKAGE_PIN F8 [get_ports RJ45_HITOR_N[3]]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]

#PORT2
set_property PACKAGE_PIN C19 [get_ports RJ45_HITOR_P[4]]
set_property PACKAGE_PIN B19 [get_ports RJ45_HITOR_N[4]]
set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]
set_property PACKAGE_PIN A17 [get_ports DOBOUT_N[4]]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
set_property KEEPER true [get_ports DOBOUT_P[4]]
set_property PACKAGE_PIN B11 [get_ports DOBOUT_N[3]]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
set_property KEEPER true [get_ports DOBOUT_P[3]]

#PORT3
set_property PACKAGE_PIN J16 [get_ports DOBOUT_N[2]]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
set_property KEEPER true [get_ports DOBOUT_P[2]]
set_property PACKAGE_PIN F18 [get_ports DOBOUT_N[1]]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
set_property KEEPER true [get_ports DOBOUT_P[1]]
set_property PACKAGE_PIN D16 [get_ports DOBOUT_N[0]]
set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
set_property KEEPER true [get_ports DOBOUT_P[0]]


#set_property PACKAGE_PIN J16 [get_ports RJ45_HITOR_N[4]]
#set_property IOSTANDARD LVDS_25 [get_ports RJ45_HITOR*]
#set_property PACKAGE_PIN F18 [get_ports DOBOUT_N[4]]
#set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
#set_property KEEPER true [get_ports DOBOUT_P[4]]
#set_property PACKAGE_PIN D16 [get_ports DOBOUT_N[3]]
#set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
#set_property KEEPER true [get_ports DOBOUT_P[3]]


#set_property PACKAGE_PIN B19 [get_ports DOBOUT_N[2]]
#set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
#set_property KEEPER true [get_ports DOBOUT_P[2]]
#set_property PACKAGE_PIN A17 [get_ports DOBOUT_N[1]]
#set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
#set_property KEEPER true [get_ports DOBOUT_P[1]]
#set_property PACKAGE_PIN B11 [get_ports DOBOUT_N[0]]
#set_property IOSTANDARD LVDS_25 [get_ports DOBOUT*]
#set_property KEEPER true [get_ports DOBOUT_P[0]]



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
