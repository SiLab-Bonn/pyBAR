# pyBAR

pyBAR - Bonn ATLAS Readout in Python and C++

Wiki page: https://github.com/SiLab-Bonn/pyBAR/wiki

Master / development branch: [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=master)](https://travis-ci.org/SiLab-Bonn/pyBAR)
[![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=development)](https://travis-ci.org/SiLab-Bonn/pyBAR)

pyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip. It uses the Basil framework to access the hardware.
pyBAR FPGA firmware and host software supports USBpix and USBpix 3.0 as well as Single Chip Adapter Card, Burn-in Card (4-chip Adapter Card) and GPAC adapter card. 

The features of the FPGA firmware in a nutshell:
- support for single chip adapter card, 4-chip adapter card (Burn-in Card) and GPAC card
- support of up to 4 FE, simultaneous readout
- continuous data taking (no interrupts during data taking, preserving all information)
- automatic data to clock phase alignment on each channel individually
- full support of EUDAQ TLU (including trigger number)
- 200kHz peak trigger rate, 50kHz continuous trigger rate (full 16 BC readout, single FE-I4)

The features of the host software in Python and C++:
- very minimalistic interface, script based, no GUI
- support for Windows/Linux/OSX
- support for FE-I4A and B
- reading configuration files from RCE/HSIO (natively) and STcontrol (converter available)
- full control over FE command generation
- sending an arbitrary bit stream/configuration sequence to FE of any desired frame length and/or format
- readout of full FE data including timestamps, storing of the compressed data to HDF5 file
- ultra fast raw data analysis, event-, cluster building and validity checking
- real time online monitor (< 100 ms latency)
- rapid development of new scan algorithms

Installation:
------------
Prerequisites:
- PyUSB (>=1.0.0rc1):

  pip install https://github.com/walac/pyusb/archive/master.zip

- pySiLibUSB (>=1.0.0):

  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/735/pySiLibUSB-2.0.3.tar.gz

- Basil (>=2.0.2):

  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/719/Basil-2.0.2.tar.gz

- progressbar (>=2.4):

  pip install progressbar-latest

Checkout pyBAR. From host folder run the following commands:

1. Build with:
   python setup.py build_ext

2. Install with:
   python setup.py develop

3. Testing:
   nosetests tests

   The scan test needs a working FE-I4.


Usage:
-----
Two methods are available:

1. Directly run scans/tunings inside the /host/pybar/scans/ folder. Just double click the .py file or run them from a IDE. This is the quick and dirty method. Very effective. Change run parameters either inside each python file (_default_run_conf dictionary) or change configuration file (configuration.yaml).
2. Use RunManager to run scans from primlist (via run_primlist() method) or to run a single scan (via run_run() method). This is the preferred method for longer sessions. Once the RunManager is initialized, it eases the way to run multiple scans/tunings in a row.

Please note the examples in the examples folder.

Support
-------
To subscribe to the pyBAR mailing list, click [here](https://e-groups.cern.ch/e-groups/EgroupsSubscription.do?egroupName=pybar-devel). Please ask questions on the pyBAR mailing list [pybar-devel@cern.ch](mailto:pybar-devel@cern.ch?subject=bug%20report%20%2F%20feature%20request) (subscription required) or file a new bug report / feature request [here](https://github.com/SiLab-Bonn/pyBAR/issues/new).

