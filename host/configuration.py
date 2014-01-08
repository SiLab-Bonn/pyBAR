import os

path = os.getcwd()  # current path

chip_flavor = 'fei4b'  # chip flavor (e.g. fei4a, fei4b)
# config_file = os.path.join(path, r'config/fei4/configs/std_cfg_' + chip_flavor + '.cfg')  # path to the FE configuration file
# config_file = os.path.join(path, r'config/fei4/configs/MDBM08_15_150_8.cfg')  # path to the FE configuration file
config_file = os.path.join(path, r'config/fei4/configs/MDBM30_15_150_8.cfg')  # path to the FE configuration file
# config_file = os.path.join(path, r'C:\Users\silab\workspace\pyBAR\host\config\SCC45/SCC45_planar.cfg')  # path to the FE configuration file
# bit_file = os.path.join(path, r'config/fpga/top.bit')  # path to the FPGA bit file (usually no need to change it)
bit_file = os.path.join(path, r'config/fpga/top_dbm_modules.bit')  # path to the FPGA bit file (usually no need to change it)
scan_data_path = os.path.join(path, r'data')  # data output path
