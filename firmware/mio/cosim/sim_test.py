#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------

import yaml
from basil.dut import Dut

# Read in the configuration YAML file
stream = open("sim.yaml", 'r')
cnfg = yaml.load(stream)

# Create the Pixel object
dut = Dut(cnfg)
dut.init()

dut['POWER_SCC']['EN_VD1'] = 1
dut['POWER_SCC']['EN_VD2'] = 1
dut['POWER_SCC']['EN_VA1'] = 1
dut['POWER_SCC']['EN_VA2'] = 1
dut['POWER_SCC'].write()

# enabling readout
dut['rx']['CH1'] = 1
dut['rx']['CH2'] = 1
dut['rx']['CH3'] = 1
dut['rx']['CH4'] = 1
dut['rx']['TLU'] = 1
dut['rx']['TDC'] = 1
dut['rx'].write()


def cmd(data, size):
    dut['cmd']['CMD_SIZE'] = size
    dut['cmd'].set_data(data)
    dut['cmd']['START']

    while not dut['cmd']['READY']:
        pass


cmd([0xB4, 0x10, 0x37, 0x00, 0x00], 39)  # settings PLL
cmd([0xB4, 0x10, 0x38, 0x04, 0x0C], 39)  # settings PLL
cmd([0xB4, 0x50, 0x70], 23)  # run mode
cmd([0xB1, 0x00], 9)  # ECR
cmd([0xB4, 0x50, 0x0E], 23)  # conf mode

dut['rx_1']['RESET']  # let rx sync

cmd([0xB4, 0x08, 0x00], 23)  # readbck a register

print('Recived data words:')
for d in dut['sram'].get_data():
    print(hex(d))
