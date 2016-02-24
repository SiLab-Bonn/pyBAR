
### pyBAR firmware for MMC3 board including readout for MIMOSA26 planes

Design is using SiTcp Ethernet module. 
To compile download free SiTcp module from: http://sitcp.bbtech.co.jp/ (need to register)<sup>1</sup>.

[Basil](https://github.com/SiLab-Bonn/basil) modules can be found here: https://github.com/SiLab-Bonn/basil/tree/development/device/modules


<sup>1</sup><sub>Use netgen (from Xilinx ISE) to generate netlist file from ngc file:
```
netgen -ofmt verilog -insert_glbl false SiTCP_XC7K_32K_BBT_V80.ngc SiTCP_XC7K_32K_BBT_V80.v
```
</sub>
