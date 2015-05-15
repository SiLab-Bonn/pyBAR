
# pyBAR [![Code Status](https://landscape.io/github/SiLab-Bonn/pyBAR/development/landscape.svg?style=flat)](https://landscape.io/github/SiLab-Bonn/pyBAR/development) [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=development)](https://travis-ci.org/SiLab-Bonn/pyBAR) [![Build Status](https://ci.appveyor.com/api/projects/status/github/SiLab-Bonn/pyBAR)](https://ci.appveyor.com/project/DavidLP/pyBAR)

pyBAR - Bonn ATLAS Readout in Python and C++

PyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip. It uses the [basil](https://github.com/SiLab-Bonn/basil) framework to access the hardware.
PyBAR's FPGA firmware and host software supports USBpix and USBpix 3.0 as well as Single Chip Adapter Card, Burn-in Card (4-chip Adapter Card) and GPAC adapter card.

PyBAR is _not only_ targeting experienced users and developers. The easy-to-use scripts allow a quick setup and start. PyBAR is a very flexible readout and test system and can be adapted to any needs.

The features of the FPGA firmware in a nutshell:
- support for single chip adapter card, 4-chip adapter card (Burn-in Card) and GPAC card
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

Prerequisites:
- PyUSB (>=1.0.0rc1):

  pip install https://github.com/walac/pyusb/archive/master.zip

- pySiLibUSB (>=1.0.0):

  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/735/pySiLibUSB-2.0.3.tar.gz

- Basil (>=2.1.0):

  pip install -e "git+https://github.com/SiLab-Bonn/basil.git@v2.1.0#egg=basil&subdirectory=host"

- progressbar (>=2.4):

  pip install progressbar-latest

- PyQtGraph:

  pip install pyqtgraph

Checkout pyBAR. From host folder run the following commands:

1. Build with:
   python setup.py build_ext

2. Install with:
   python setup.py develop

3. Testing:
   nosetests tests

   Note: the tests need a working FE-I4 setup.


## Usage

Two methods are available:

1. Directly run scans and tunings from the [scans](/host/pybar/scans) folder. Just double click the .py file or run the script from an IDE or use a shell. This is the quick and dirty method. Very effective. To change run parameters, two methods are supported: either change _default_run_conf dictionary of the run script inside the [scans](/host/pybar/scans) folder or change the [configuration.yaml](/host/pybar/configuration.yaml) (examples are inside the file).
2. Use RunManager to run scans from primlist (via run_primlist() method) or to run a single scan (via run_run() method). This is the preferred method for longer sessions. Once the RunManager is initialized, it eases the way to run multiple scans/tunings in a row. Run parameters and FE configuration can be changed in between the runs.

Please note the examples in the [examples](/host/examples) folder.

Also note our [Wiki](https://github.com/SiLab-Bonn/pyBAR/wiki).

## Support

To subscribe to the pyBAR mailing list, click [here](https://e-groups.cern.ch/e-groups/EgroupsSubscription.do?egroupName=pybar-devel). Please ask questions on the pyBAR mailing list [pybar-devel@cern.ch](mailto:pybar-devel@cern.ch?subject=bug%20report%20%2F%20feature%20request) (subscription required) or file a new bug report / feature request [here](https://github.com/SiLab-Bonn/pyBAR/issues/new).

