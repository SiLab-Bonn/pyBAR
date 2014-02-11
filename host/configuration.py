import os

path = os.getcwd()  # current path

chip_flavor = 'fei4a'  # chip flavor (e.g. fei4a, fei4b)

device_configuration = {
    "configuration_file": os.path.join(path, r'config/fei4/configs/std_cfg_' + chip_flavor + '.cfg'),  # path to the FE configuration file
    "definition_file": None,  # path to the FE XML file
    "bit_file": os.path.join(path, r'config/fpga/top.bit'),  # path to the FPGA bit file
    "force_download": False,  # force download of FPGA bit file
    "device": None,  # specify USB device (device ID)
    "scan_data_path": os.path.join(path, r'data'),  # data output path
    "device_identifier": "",  # additional device identifier
    "invert_rx_data": False # enable for DBM modules
}
