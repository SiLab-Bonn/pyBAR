
# pyBAR [![Code Status](https://landscape.io/github/SiLab-Bonn/pyBAR/master/landscape.svg?style=flat)](https://landscape.io/github/SiLab-Bonn/pyBAR/master) [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=master)](https://travis-ci.org/SiLab-Bonn/pyBAR) [![Build Status](https://ci.appveyor.com/api/projects/status/github/SiLab-Bonn/pyBAR?svg=true)](https://ci.appveyor.com/project/DavidLP/pybar-71xwl)

pyBAR - Bonn ATLAS Readout in Python and C++

PyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip. It uses the [basil](https://github.com/SiLab-Bonn/basil) framework to access the readout hardware.
PyBAR's FPGA firmware and host software includes support for different hardware platforms.

PyBAR is _not only_ targeting experienced users and developers. The easy-to-use scripts allow a quick setup and start. PyBAR is a very flexible readout and test system and can be adapted to any needs.

The features of the FPGA firmware in a nutshell:
- supported readout hardware:
  MIO, MIO 3.0, SEABAS2, Avnet LX9 and Digilent Nexys<sup>TM</sup>4 DDR
- supported adapter cards:
  Single Chip Adapter Card, Burn-in Card (Quad Module Adapter Card) and the General Purpose Analog Card (GPAC)
- support of up to 4 FE, simultaneous readout
- continuous data taking (no interrupts during data taking, preserving all information)
- automatic data to clock phase alignment on each channel individually
- full support of EUDAQ Telescope/TLU
- 200kHz peak trigger rate, 50kHz continuous trigger rate (full 16 BC readout, single FE-I4)

The features of the host software in Python and C++:
- very minimalistic interface, script based, no GUI
- support for Windows/Linux/OSX
- support for FE-I4A and B
- configuration files human readable (compatible to RCE/HSIO)
- full control over FE command generation
- sending any arbitrary bit stream/configuration sequence to the FE of any desired frame length and/or format
- readout of full FE data including timestamps, storing of the compressed data to HDF5 file
- ultra fast raw data analysis, event-, cluster building and validity checking
- real-time online monitor (< 100 ms latency)
- rapid development and implementation of new scan algorithms

## Installation

For USB support, PyBAR requires the following packages:
- [PyUSB](https://github.com/walac/pyusb) (>=1.0.0rc1):
  ```
  pip install "git+https://github.com/walac/pyusb.git@master"
  ```
  
- [pySiLibUSB](https://silab-redmine.physik.uni-bonn.de/projects/pysilibusb) (>=2.0.0):
  ```
  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/800/pySiLibUSB-2.0.5.tar.gz
  ```

[Basil](https://github.com/SiLab-Bonn/basil) (==2.1.2) is required:
  ```
  pip install -e "git+https://github.com/SiLab-Bonn/basil.git@development#egg=basil&subdirectory=host"
  ```

The following packages are required for pyBAR's core functionality:
  ```
  bitarray cython matplotlib numpy pandas progressbar-latest tables pyyaml scipy
  ```

For full functionality, the following additional packages are needed:
  ```
  mock nose pyqtgraph pyserial pyvisa pyvisa-py pyzmq
  ```

On Windows, the `pywin32` package is required.

The installation procedure depends on the operating system and software environment.
Please read our [Step-by-step Installation Guide](https://github.com/SiLab-Bonn/pyBAR/wiki/Step-by-step-Installation-Guide) carefully.

Clone pyBAR from git and then run the following commands from the within project folder:

1. Build with:
   ```
   python setup.py build_ext
   ```

2. Install with:
   ```
   python setup.py develop
   ```

3. Testing (from within the tests folder):
   ```
   nosetests test_analysis.py
   ```

## Usage

Please note the [Wiki](https://github.com/SiLab-Bonn/pyBAR/wiki) and the [User Guide](https://github.com/SiLab-Bonn/pyBAR/wiki/User-Guide).

## Support

To subscribe to the pyBAR mailing list, click [here](https://e-groups.cern.ch/e-groups/EgroupsSubscription.do?egroupName=pybar-devel). Please ask questions on the pyBAR mailing list [pybar-devel@cern.ch](mailto:pybar-devel@cern.ch?subject=bug%20report%20%2F%20feature%20request) (subscription required) or file a new bug report / feature request [here](https://github.com/SiLab-Bonn/pyBAR/issues/new).

