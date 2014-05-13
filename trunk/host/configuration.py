import os

path = os.getcwd()  # current path

chip_flavor = 'fei4a'  # chip flavor (e.g. fei4a, fei4b)

default_configuration = {
    "configuration_file": os.path.join(path, r'config/fei4/configs/std_cfg_' + chip_flavor + '.cfg'),  # path to the FE configuration file
    "register": None,  # FE register object
    "definition_file": None,  # path to the FE XML file
    "bit_file": os.path.join(path, r'config/fpga/top.bit'),  # path to the FPGA bit file
    "force_download": False,  # force download of FPGA bit file
    "device_id": '',  # device ID (aka board ID)
    "device": None,  # specify USB device (e.g. SiUSBDevice object)
    "scan_data_path": os.path.join(path, r'data'),  # data output path
    "module_id": 'test module',  # additional module identifier
    "invert_rx_data": False  # enable for DBM modules
}
