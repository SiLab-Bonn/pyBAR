
# pyBAR [![Code Status](https://landscape.io/github/SiLab-Bonn/pyBAR/master/landscape.svg?style=flat)](https://landscape.io/github/SiLab-Bonn/pyBAR/master) [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=master)](https://travis-ci.org/SiLab-Bonn/pyBAR) [![Build Status](https://ci.appveyor.com/api/projects/status/github/SiLab-Bonn/pyBAR?svg=true)](https://ci.appveyor.com/project/DavidLP/pybar-71xwl)

pyBAR - Bonn ATLAS Readout in Python and C++

PyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip. It uses the [basil](https://github.com/SiLab-Bonn/basil) framework to access the readout hardware.
PyBAR's FPGA firmware and host software includes support for different hardware platforms.

PyBAR is *not only* targeting experienced users and developers. The easy-to-use scripts allow a quick setup and start. PyBAR is a very flexible readout and test system and can be adapted to any needs.

The features of the FPGA firmware in a nutshell:
- supported readout hardware:
  MIO, MIO3/MMC3, Avnet LX9 and Digilent Nexys<sup>TM</sup>4 DDR
- supported adapter cards:
  Single Chip Adapter Card, Burn-in Card (Quad Module Adapter Card) and the General Purpose Analog Card (GPAC)
- support of up to 4 FE, simultaneous readout
- continuous data taking (no interrupts during data taking, preserving all information)
- automatic data to clock phase alignment on each channel individually
- full support of EUDAQ TLU and availability of EUDAQ Producer

The features of the host software in Python and C++:
- very minimalistic interface, script based, no GUI
- support for Windows/Linux/OSX
- support for FE-I4A and B
- configuration files human readable (compatible to RCE/HSIO)
- full control over FE command generation
- sending any arbitrary bit stream/configuration sequence to the FE of any desired frame length and/or format
- readout of full FE data including timestamps, storing of the compressed data to HDF5 file
- ultra fast raw data analysis, event-, cluster building and validity checking
- real-time online monitor with GUI
- fast development and implementation of new scan algorithms

## Installation

The following packages are required for pyBAR's core functionality:
  ```
  basil_daq bitarray cython matplotlib numba numpy pixel_clusterizer progressbar-latest pytables pyyaml scipy
  ```

For full functionality, the following additional packages are required:
  ```
  ipython mock nose pyqtgraph pyserial pyvisa pyvisa-py pyzmq sphinx vitables
  ```

Run the **following commands** to install the packages:
  ```
  conda install bitarray cython ipython matplotlib mock nose numba numpy pyserial pytables pyyaml pyzmq scipy sphinx

  pip install progressbar-latest pyvisa pyvisa-py git+https://github.com/pyqtgraph/pyqtgraph.git@pyqtgraph-0.10.0
  ```

On Windows, the `pywin32` package is required:
  ```
  conda install pywin32
  ```

[Basil](https://github.com/SiLab-Bonn/basil) (==2.4.6) is required:
  ```
  pip install basil_daq==2.4.6
  ```

[pyBAR FEI4 Interpreter](https://github.com/SiLab-Bonn/pyBAR_fei4_interpreter) (>=1.3.0) is required:
  ```
  pip install git+https://github.com/SiLab-Bonn/pyBAR_fei4_interpreter@1.3.0
  ```

[Pixel Clusterizer](https://github.com/SiLab-Bonn/pixel_clusterizer) (>=3.0.0) is required:
  ```
  pip install git+https://github.com/SiLab-Bonn/pixel_clusterizer@development
  ```

To enable support for USB devices (MIO, MIO3 and MMC3), the following additional packages are required:
- [PyUSB](https://github.com/walac/pyusb) (>=1.0.0rc1):
  ```
  pip install pyusb
  ```

- [pySiLibUSB](https://github.com/SiLab-Bonn/pySiLibUSB) (>=2.0.0):
  ```
  pip install pySiLibUSB
  ```

The installation procedure depends on the operating system and software environment.
Please read our [Step-by-step Installation Guide](https://github.com/SiLab-Bonn/pyBAR/wiki/Step-by-step-Installation-Guide) carefully.

After the obove steps are completed, clone the pyBAR git repository and then run the following commands from the within project folder:

1. Install with:
   ```
   python setup.py develop
   ```

2. Testing (from within the pybar/testing folder):
   ```
   nosetests test_analysis.py
   ```

## Usage

Please note the [Wiki](https://github.com/SiLab-Bonn/pyBAR/wiki) and the [User Guide](https://github.com/SiLab-Bonn/pyBAR/wiki/User-Guide).

## Support

To subscribe to the pyBAR mailing list, click [here](https://e-groups.cern.ch/e-groups/EgroupsSubscription.do?egroupName=pybar-devel). Please ask questions on the pyBAR mailing list [pybar-devel@cern.ch](mailto:pybar-devel@cern.ch?subject=bug%20report%20%2F%20feature%20request) (subscription required) or file a new bug report / feature request [here](https://github.com/SiLab-Bonn/pyBAR/issues/new).

