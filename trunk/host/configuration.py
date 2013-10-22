import os

path = os.getcwd()

chip_flavor = 'fei4b'
config_file = os.path.join(path, r'config/fei4/configs/std_cfg_'+chip_flavor+'.cfg')
bit_file = os.path.join(path, r'config/fpga/top.bit')
scan_data_path = os.path.join(path, r'data')
