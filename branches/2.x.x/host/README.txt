pyBAR - Bonn ATLAS Readout in Python and C++
https://silab-redmine.physik.uni-bonn.de/projects/pybar

pyBAR is a versatile readout and test system for ATLAS FE-I4(A/B) pixel readout chip. It is uses the Basil framework to access the hardware.
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
- ultra fast raw data analysis and validity checking
- rapid development of new scan algorithms

Installation:
------------
Prerequisites:
- PyUSB (>=1.0.0rc1):
  pip install https://github.com/walac/pyusb/archive/master.zip
- pySiLibUSB (>=1.0.0):
  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/667/pySiLibUSB-2.0.0.zip
- Basil (>=2.0.0):
  pip install https://silab-redmine.physik.uni-bonn.de/attachments/download/671/Basil-2.0.0.zip
- progressbar (>=2.4):
  pip install progressbar-latest

Checkout pyBAR. From host folder run the following commands:

1. Build with:
python setup.py build_ext

2. Install with:
python setup.py develop

3. Testing built:
Run tests from tests folder.

Usage:
-----
Two methods are available:
1. Directly run scans/tunings inside the /host/pybar/scans/ folder. Just double click the .py file or run them from a IDE.
   This is the quick and dirty method. Very effective. Change run parameters either inside each python file (_default_run_conf) or change configuration file (configuration.yaml).
2. Use RunManager to run scans from primlist (via run_primlist() method) or to run a single scan (via run_run() method).
   This is the preferred method for longer sessions. Once the RunManager is initialized, it eases the way to run multiple scans/tunings in a row.
   An interactive python shell (e.g. IPython) makes the workflow even simpler.

Please read the examples in the examples folder.
