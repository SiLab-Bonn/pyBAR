import os

path = os.getcwd()  # current path

chip_flavor = 'fei4a'  # chip flavor (e.g. fei4a, fei4b)

default_configuration = {
    "dut": "pybar.yaml",  # set DUT (hardware configuration)
    "configuration_file": os.path.join(path, r'config/fei4/configs/std_cfg_' + chip_flavor + '.cfg'),  # path to the FE configuration file, text (.cfg) or HDF5 (.h5) file
    "register": None,  # FE register object
    "definition_file": None,  # path to the FE XML file
    "bit_file": os.path.join(path, r'config/fpga/top.bit'),  # path to the FPGA bit file
    "force_download": False,  # force download of FPGA bit file, if false, FPGA configuration will not be overwritten during initialization
    "device_id": "",  # device ID (aka board ID), use None or empty string for any connected USB card
    "device": None,  # specify USB device (e.g. SiUSBDevice object)
    "scan_data_path": os.path.join(path, r'data'),  # data output path
    "module_id": "test module",  # additional module identifier, an extra sub-directory in data directory will be generated
    "invert_rx_data": False  # change Rx_p and Rx_n data lines for DBM modules
}
