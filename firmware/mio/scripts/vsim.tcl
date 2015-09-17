# ----------------------------------------------------------------
# TO RUN (in work directory):
# cd into the directory where this file is located
# set XILINX, BASIL, FEI4 variable (see below)
# source vsim.tcl
# vlog_libs (needed once)
# vlog_top
# vsim_top
# wave_top
# restart -f (to clear waveforms)
# run 1ms
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# set system environment XILINX to ISE directory
# ----------------------------------------------------------------
set XILINX "C:/Xilinx/14.7/ISE_DS/ISE"
#set XILINX   $env(XILINX)

# ----------------------------------------------------------------
#set path to basil
# ----------------------------------------------------------------
set BASIL "../../../../../../basil"

# ----------------------------------------------------------------
#set path to FEI4 model
# ----------------------------------------------------------------
set FEI4 "../../../../../../fei4/trunk/models/fei4a"

# ----------------------------------------------------------------
# run Xilinx->EDK->Compile Simulation libraries
# copy latest C:\Xilinx\xx.x\ISE_DS\EDK\modelsim.ini to work folder
# ----------------------------------------------------------------

# ----------------------------------------------------------------
#map liblaries - this can be different on other platforms than Windows
#vmap unisims_ver $XILINX/EDK/unisims_ver
#vmap simprims_ver $XILINX/EDK/simprims_ver
# or
#vmap unisims_ver $XILINX/ISE/verilog/questasim/10.1c/lin64/unisims_ver
#vmap simprims_ver $XILINX/ISE/verilog/questasim/10.1c/lin64/simprims_ver 
# ----------------------------------------------------------------

proc vlog_libs {} {
    
    global XILINX
    vlib simprims_ver
    vlog -work simprims_ver $XILINX/verilog/src/simprims/*.v

    vlib unisims_ver
    vlog -work unisims_ver $XILINX/verilog/src/unisims/*.v
}

proc vlog_top {} {

    global XILINX
    global BASIL
    global FEI4
    
    if {[file exists "work"] == 1} {
        echo "Deleting old work library ..."
        vdel -all -lib work
    }

    vlib work

    vlog $XILINX/verilog/src/glbl.v

    vlog -lint $BASIL/firmware/modules/utils/*.v +incdir+$BASIL/firmware/modules/includes
    vlog -lint $BASIL/firmware/modules/sram_fifo/*.v
    vlog -lint $BASIL/firmware/modules/fei4_rx/*.v
    vlog -lint $BASIL/firmware/modules/cmd_seq/*.v
    vlog -lint $BASIL/firmware/modules/rrp_arbiter/*.v +incdir+$BASIL/firmware/modules/rrp_arbiter
    vlog -lint $BASIL/firmware/modules/tlu/*.v
    vlog -lint $BASIL/firmware/modules/tdc_s3/*.v
    vlog -lint $BASIL/firmware/modules/gpio/*.v
    
    vlog ../src/top.v
    vlog ../src/clk_gen.v

    vlog  -novopt $FEI4/fei4_top.sv +incdir+$FEI4 +define+TEST_DC=1
    vlog  +incdir+$FEI4 +incdir+$BASIL/firmware/modules/tb +incdir+../tb ../tb/top_tb.sv

    #vlog ../ise/netgen/par/top_timesim.v
}

proc vsim_top {} {
    vsim -novopt -t 1ps -L unisims_ver  work.top_tb glbl
    #vsim -novopt -t 1ps -L unisims_ver  -L simprims_ver work.top_tb glbl
}

proc wave_top {} {
    add wave -group top sim:/top_tb/*
    add wave -group uut sim:/top_tb/uut/*
    add wave -group clkgen sim:/top_tb/uut/iclkgen/*

    add wave -group cmd sim:/top_tb/uut/icmd/i_cmd_seq_core/*
    add wave -group fifo_sram sim:/top_tb/uut/i_out_fifo/i_sram_fifo/*

    add wave -group fei4_rx_0 {sim:/top_tb/uut/rx_gen[0]/ifei4_rx/i_fei4_rx_core/*}
    add wave -group tlu sim:/top_tb/uut/i_tlu_controller/i_tlu_controller_core/*
    add wave -group tlu_fsm sim:/top_tb/uut/i_tlu_controller/i_tlu_controller_core/tlu_controller_fsm_inst/*
    add wave -group tdc sim:/top_tb/uut/i_tdc/i_tdc_s3_core/*
    # new arbiter
    add wave -group arbiter sim:/top_tb/uut/i_rrp_arbiter/*
    # old arbiter
    #add wave -group old_arbiter sim:/top_tb/uut/arbiter_inst/*
    
    #add wave -group pa sim:/top_tb/uut/ifei4_rx/ireceiver_logic/irec_sync/iphase_align/*
    #add wave -group rec_sync sim:/top_tb/uut/ifei4_rx/ireceiver_logic/irec_sync/*
    #add wave -group rec_logic sim:/top_tb/uut/ifei4_rx/ireceiver_logic/*
    #add wave -group rx sim:/top_tb/uut/ifei4_rx/*
    #add wave -group fei4 sim:/top_tb/fei4_inst/*
    #add wave -group fei4_cmd sim:/top_tb/fei4_inst/i_CMD/*
    #add wave -group fei4_dob sim:/top_tb/fei4_inst/i_DOB/*
    #add wave -group fei4_eochl sim:/top_tb/fei4_inst/i_EOCHL/*

    #add wave -group fei4_c0_r0 {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/*}
    #add wave -group fei4_c0_r0_core {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/*}
    #add wave -group fei4_darray {sim:/top_tb/fei4_inst/i_digital_array/*}
    #add wave -group fei4_aarray {sim:/top_tb/fei4_inst/i_FEND_DIGI_ARRAY/*}
    #add wave -group fei4_aarray_0_0 {sim:/top_tb/fei4_inst/i_FEND_DIGI_ARRAY/genblk1[0]/DC_INST/genblk1[0]/PIX_L/*}
    #add wave -group fei4_c0_r0_m0 {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/latency_mem[0]/mem/*}

}

