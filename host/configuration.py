import os

path = os.getcwd()

chip_flavor = 'fei4b'
config_file = os.path.join(path, r'config/fei4default/configs/std_cfg_'+chip_flavor+'.cfg')
bit_file = os.path.join(path, r'config/FPGA/top.bit')
outdir = os.path.join(path, r'data')
