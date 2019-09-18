
# pyBAR [![Build Status](https://travis-ci.org/SiLab-Bonn/pyBAR.svg?branch=development)](https://travis-ci.org/SiLab-Bonn/pyBAR/branches) [![Build Status](https://ci.appveyor.com/api/projects/status/github/SiLab-Bonn/pyBAR?branch=development&svg=true)](https://ci.appveyor.com/project/laborleben/pybar-71xwl?branch=development)

pyBAR - Bonn ATLAS Readout in Python

## Intended Use

PyBAR is a versatile readout and test system for the ATLAS FEI4(A/B) pixel readout chip. It uses the [basil](https://github.com/SiLab-Bonn/basil) framework to access the readout hardware.
PyBAR's host software supports different hardware platforms for which FPGA firmware is provided.

### Features

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

Python 2.7 or Python 3.7 or higher must be used (other Python versions are not guaranteed to work). There are many ways to install Python, though we recommend using [Anaconda Python](https://www.anaconda.com/distribution/) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html).

### Prerequisites

The following packages are required for pyBAR's core functionality:
  ```
  basil_daq bitarray contextlib2 cython matplotlib numba numpy pixel_clusterizer pytables pyyaml scipy tqdm
  ```

For full functionality, the following additional packages are required:
  ```
  ipython mock nose pyqtgraph pyserial pyvisa pyvisa-py pyzmq vitables
  ```

Run the **following commands** to install the packages:
  ```
  conda install bitarray contextlib2 cython ipython matplotlib mock nose numba numpy pyqt pyserial pytables pyyaml pyzmq qtpy scipy

  pip install pyvisa pyvisa-py git+https://github.com/pyqtgraph/pyqtgraph.git@pyqtgraph-0.10.0 tqdm
  ```

[Basil](https://github.com/SiLab-Bonn/basil) (>=2.4.12,<4.0.0) is required:
  ```
  pip install "basil_daq>=2.4.12,<4.0.0"
  ```

[pyBAR FEI4 Interpreter](https://github.com/SiLab-Bonn/pyBAR_fei4_interpreter) (>=1.5,<2.0) is required:
  ```
  pip install "pyBAR_fei4_interpreter>=1.5,<2.0"
  ```

[Pixel Clusterizer](https://github.com/SiLab-Bonn/pixel_clusterizer) (>=3.1,<3.2) is required:
  ```
  pip install "pixel_clusterizer>=3.1,<3.2"
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

### Installation of pyBAR

After the obove steps are completed, clone the pyBAR git repository.

1. Use the following command to install pyBAR (from within the repository folder):
   ```
   pip install -e .
   ```

2. For testing the basic functionality of pyBAR, execute the following command (from within the pybar/testing folder):
   ```
   nosetests test_analysis.py
   ```

## Usage

Please note the [Wiki](https://github.com/SiLab-Bonn/pyBAR/wiki) and the [User Guide](https://github.com/SiLab-Bonn/pyBAR/wiki/User-Guide).

## Contributing to pyBAR

### Bug Report / Feature Request / Question

Please use GitHub's [issue tracker](https://github.com/SiLab-Bonn/pyBAR/issues).

*For CERN users*: Feel free to subscribe to the [pyBAR mailing list](https://e-groups.cern.ch/e-groups/EgroupsSubscription.do?egroupName=pybar-devel).

### Contributing Code to pyBAR

1. Fork the project.
2. Clone your fork and/or get the latest changes from upstream.
2. Create a topic branch.
3. Modify the code and commit your changes in logical chunks.
4. Locally rebase the upstream branch into your topic branch.
5. Push your topic branch to your fork.
6. Open a [Pull Request (PR)](https://help.github.com/en/articles/about-pull-requests) with clear title and description about the modifications.

## Publications

The pyBAR readout system was extensively used for various high-energy particle physics experiments and for detector R&D.

### Proceedings and Papers

1. Serially powered pixel detector prototype (at Bonn) for the ATLAS High-Luminosity LHC (HL-LHC) upgrade (24 FEI4 chips). DOI: [10.1088/1748-0221/12/03/c03045](https://doi.org/10.1088/1748-0221/12/03/c03045), DOI: [10.1088/1748-0221/12/03/p03004](https://doi.org/10.1088/1748-0221/12/03/p03004)
2. Stave 0 demonstrator (at CERN) for the ATLAS High-Luminosity LHC (HL-LHC) upgrade (28 FEI4 chips): document in preparation
3. [SHiP experiment](https://cds.cern.ch/record/2286844) at the CERN Super Proton Synchrotron (SPS) facility to help with the track reconstruction (24 FEI4 chips): document in preparation
4. BEAST/TPC experiment at the SuperKEKB facility to measure the beam/radiation background (8 FEI4 chips). DOI: [10.1016/j.nima.2018.05.071](https://doi.org/10.1016/j.nima.2018.05.071)
5. BEAST/FANGS experiment at the SuperKEKB facility to measure the beam/radiation background (15 FEI4 chips): document in preparation
6. TPC to measure nuclear recoil for dark matter search. DOI: [10.1016/j.nima.2019.06.037](https://dx.doi.org/10.1016/j.nima.2019.06.037)
7. Detector tests (pCVD diamond) for the ATLAS Diamond Beam Monitor (DBM) and implementation of a novel threshold tuning method. DOI: [10.1088/1748-0221/12/03/C03072](https://dx.doi.org/10.1088/1748-0221/12/03/C03072)
8. Beam monitor for the [beamline for detector tests](http://accelconf.web.cern.ch/AccelConf/IPAC2013/papers/thpfi006.pdf) at ELSA, Bonn, Germany.
9. Various other detector tests at [CERN SPS](http://sba.web.cern.ch) (Geneva, Switzerland), [DESY II](https://testbeam.desy.de) (Hamburg, Germany), and [ELSA](https://www-elsa.physik.uni-bonn.de) (Bonn, Germany).
    - Silicon detecors: DOI: [10.1088/1748-0221/12/06/P06020](https://dx.doi.org/10.1088/1748-0221/12/06/P06020)
    - 3D pCVD diamond detectors: document submitted
