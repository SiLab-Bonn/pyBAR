
# pyBAR [![Code Status](https://landscape.io/github/SiLab-Bonn/pyBAR/master/landscape.svg?style=flat)](https://landscape.io/github/SiLab-Bonn/pyBAR/master) [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=master)](https://travis-ci.org/SiLab-Bonn/pyBAR) [![Build Status](https://ci.appveyor.com/api/projects/status/github/SiLab-Bonn/pyBAR?svg=true)](https://ci.appveyor.com/project/DavidLP/pybar-71xwl)

pyBAR - Bonn ATLAS Readout in Python

PyBAR is a versatile readout and test system for the ATLAS FEI4(A/B) pixel readout chip. It uses the [basil](https://github.com/SiLab-Bonn/basil) framework to access the readout hardware.
PyBAR's FPGA firmware and host software includes support for different hardware platforms.

PyBAR is *not only* targeting experienced users and developers. The easy-to-use scripts allow a quick setup and start. PyBAR is a very flexible readout and test system and provides the capability to conduct tests and characterization measurements of individual chips, and tests of large-scale detectors with multiple multi-chip modules and multiple readout boards.

The features of the FPGA firmware in a nutshell:
- supported readout boards:
  any hardware that is supported by basil (e.g., MIO2, MIO3, and MMC3)
- supported adapter cards:
  Single Chip Adapter Card, Burn-in Card (Quad Module Adapter Card) and the General Purpose Analog Card (GPAC)
- readout of multiple readout boards
- readout of multiple multi-chip modules (e.g., single, dual, quad module, and any combination of those)
- simultaneous readout (e.g., data taking with external trigger, individual tuning of chips)
- continuous data taking
- individual and automatic data to clock phase alignment on each channel
- full support of EUDAQ TLU and availability of EUDAQ Producer

The features of the host software in Python:
- no GUI
- support for Windows, Linux and macOS
- scan/tuning/calibration algorithms are implemented in stand-alone scripts
- scripts are implemented for operating single chips but are working with multi-chip configurations as well
- fast development and implementation of new scan/tuning/calibration algorithms
- configuration files are human readable (compatible to RCE/HSIO)
- full control over FEI4 command generation, sending any arbitrary bit stream and configuration sequence to the FEI4
- recording of the full input data stream with timestamps and storage of the compressed data to HDF5 files
- ultra fast raw data analysis, event and cluster building, and raw data validity checks
- real-time online monitor with GUI

## Installation

The following packages are required for pyBAR's core functionality:
  ```
  basil_daq bitarray contextlib2 cython matplotlib numba numpy pixel_clusterizer progressbar-latest pytables pyyaml scipy
  ```

For full functionality, the following additional packages are required:
  ```
  ipython mock nose pyqtgraph pyserial pyvisa pyvisa-py pyzmq sphinx vitables
  ```

Run the **following commands** to install the packages:
  ```
  conda install python=2.7 bitarray contextlib2 cython ipython matplotlib mock nose numba numpy pyqt pyserial pytables pyyaml pyzmq qtpy scipy sphinx

  pip install progressbar-latest pyvisa pyvisa-py git+https://github.com/pyqtgraph/pyqtgraph.git@pyqtgraph-0.10.0
  ```

On Windows, the `pywin32` package is required:
  ```
  conda install pywin32
  ```

[Basil](https://github.com/SiLab-Bonn/basil) (>=2.4.9,<3.0.0) is required:
  ```
  pip install 'basil_daq>=2.4.9,<3.0.0'
  ```

[pyBAR FEI4 Interpreter](https://github.com/SiLab-Bonn/pyBAR_fei4_interpreter) (>=1.3.0) is required:
  ```
  pip install git+https://github.com/SiLab-Bonn/pyBAR_fei4_interpreter@development
  ```

[Pixel Clusterizer](https://github.com/SiLab-Bonn/pixel_clusterizer) (>=3.1,<3.2) is required:
  ```
  pip install 'pixel_clusterizer>=3.1,<3.2'
  ```

To enable support for USB devices (MIO2), the following additional packages are required:
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

