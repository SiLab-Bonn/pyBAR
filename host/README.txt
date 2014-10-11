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
