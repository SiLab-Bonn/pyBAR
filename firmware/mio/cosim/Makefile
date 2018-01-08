#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

PWD=$(shell pwd)

#SIMULATION_HOST?=localhost
#SIMULATION_PORT?=12345
SIMULATION_BUS?=basil.utils.sim.SiLibUsbBusDriver
SIMULATION_END_ON_DISCONNECT?=1

#export SIMULATION_HOST
#export SIMULATION_PORT
export SIMULATION_BUS
export SIMULATION_END_ON_DISCONNECT

#to make life bit easier
#PYTHONLIBS=$(shell python -c 'from distutils import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
#export LD_LIBRARY_PATH+=$(PYTHONLIBS)
#export PYTHONPATH+=$(shell python -c "from distutils import sysconfig; print(sysconfig.get_python_lib())"):$(COCOTB)
#export PYTHONHOME=$(shell python -c "from distutils.sysconfig import get_config_var; print(get_config_var('prefix'))")
export PYTHONHOME=$(shell python -c "from distutils.sysconfig import get_config_var; print(get_config_var('prefix'))")

# Must have XILINX set as an environment variable.
# i.e. export XILINX=~/Xilinx/14.7/ISE_DS
XILINX_SRC?=$(XILINX)

BASIL?=$(shell python -c "import basil;import os;print os.path.dirname(basil.__file__)")
BASIL_MODULES?=$(BASIL)/../firmware/modules
FEI4_SOURCES?=$(BASIL)/../../fei4/trunk/models/fei4a
PYBAR?=$(shell python -c "import pybar;import os;print os.path.dirname(pybar.__file__)")
PYBAR_SOURCES?=$(PYBAR)/../firmware/mio

VERILOG_SOURCES = \
                  $(PYBAR_SOURCES)/cosim/tb.sv \
                  $(PYBAR_SOURCES)/src/top.v \
                  $(PYBAR_SOURCES)/src/clk_gen.v \
                  $(XILINX_SRC)/unisims/IFDDRRSE.v \
                  $(XILINX_SRC)/unisims/BUFG.v \
                  $(XILINX_SRC)/unisims/OFDDRRSE.v \
                  $(XILINX_SRC)/unisims/DCM.v \
                  $(XILINX_SRC)/unisims/FDDRRSE.v \
                  $(XILINX_SRC)/unisims/FDRSE.v \
                  $(XILINX_SRC)/unisims/IBUF.v \
                  $(XILINX_SRC)/unisims/OBUF.v \
                  $(XILINX_SRC)/unisims/INV.v \
                  $(XILINX_SRC)/unisims/IBUFG.v \
                  $(XILINX_SRC)/unisims/IDDR.v \
                  $(XILINX_SRC)/unisims/SRL16.v \
                  $(XILINX_SRC)/unisims/ODDR.v \
                  $(XILINX_SRC)/unisims/SRLC16E.v \
                  $(XILINX_SRC)/unisims/FD.v \
                  $(XILINX_SRC)/unisims/FDS.v \
                  $(XILINX_SRC)/unisims/OR2.v \
                  $(XILINX_SRC)/unisims/OR3.v \
                  $(BASIL_MODULES)/utils/reset_gen.v \
                  $(BASIL_MODULES)/utils/clock_divider.v \
                  $(BASIL_MODULES)/utils/bus_to_ip.v \
                  $(BASIL_MODULES)/utils/fx2_to_bus.v \
                  $(BASIL_MODULES)/utils/flag_domain_crossing.v \
                  $(BASIL_MODULES)/utils/3_stage_synchronizer.v \
                  $(BASIL_MODULES)/utils/ddr_des.v \
                  $(BASIL_MODULES)/utils/cdc_pulse_sync.v \
                  $(BASIL_MODULES)/utils/cdc_syncfifo.v \
                  $(BASIL_MODULES)/utils/generic_fifo.v \
                  $(BASIL_MODULES)/tdc_s3/tdc_s3.v \
                  $(BASIL_MODULES)/tdc_s3/tdc_s3_core.v \
                  $(BASIL_MODULES)/tlu/tlu_controller.v \
                  $(BASIL_MODULES)/tlu/tlu_controller_fsm.v \
                  $(BASIL_MODULES)/tlu/tlu_controller_core.v \
                  $(BASIL_MODULES)/gpio/gpio.v \
                  $(BASIL_MODULES)/fei4_rx/fei4_rx_core.v \
                  $(BASIL_MODULES)/fei4_rx/receiver_logic.v \
                  $(BASIL_MODULES)/fei4_rx/sync_master.v \
                  $(BASIL_MODULES)/fei4_rx/rec_sync.v \
                  $(BASIL_MODULES)/fei4_rx/decode_8b10b.v \
                  $(BASIL_MODULES)/fei4_rx/fei4_rx.v \
                  $(BASIL_MODULES)/cmd_seq/cmd_seq.v \
                  $(BASIL_MODULES)/cmd_seq/cmd_seq_core.v \
                  $(BASIL_MODULES)/sram_fifo/sram_fifo.v \
                  $(BASIL_MODULES)/sram_fifo/sram_fifo_core.v \
                  $(BASIL_MODULES)/rrp_arbiter/rrp_arbiter.v \
                  $(XILINX_SRC)/glbl.v

COMPILE_ARGS = -g2012 -DTEST_DC=1 -I$(BASIL_MODULES) -I$(BASIL_MODULES)/tb -I../tb -I$(FEI4_SOURCES)

TOPLEVEL = tb
MODULE   = basil.utils.sim.Test

include $(COCOTB)/makefiles/Makefile.inc
include $(COCOTB)/makefiles/Makefile.sim

sim_only: $(CUSTOM_SIM_DEPS) $(COCOTB_LIBS) $(COCOTB_VPI_LIB) $(CUSTOM_COMPILE_DEPS)
	PYTHONPATH=$(LIB_DIR):$(SIM_ROOT):$(PWD):$(NEW_PYTHONPATH) $(LIB_LOAD) MODULE=$(MODULE) \
	TESTCASE=$(TESTCASE) TOPLEVEL=$(TOPLEVEL) \
	vvp -M $(LIB_DIR) -m gpivpi $(SIM_BUILD)/sim.vvp $(SIM_ARGS) $(EXTRA_ARGS) $(PLUSARGS) -fst
