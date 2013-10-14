# ----------------------------------------------------------------
# TO RUN (in work directory):
# source vsim.tcl
# vlog_top
# vsim_top
# wave_top
# run 1ms
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# set system envioremtn XILINX to ISE directory
# or set XILINX "C:/Xilinx/14.6/ISE_DS"
# ----------------------------------------------------------------
set XILINX   $env(XILINX)

# ----------------------------------------------------------------
#set path to basil
# ----------------------------------------------------------------
set BASIL "../../../../../.."

# ----------------------------------------------------------------
# run Xilinx->EDK->Compile Simulation Librarie
# copy latest C:\Xilinx\xx.x\ISE_DS\EDK\modelsim.ini to work folder
# ----------------------------------------------------------------

# ----------------------------------------------------------------
#map liblaries - on windows or diffrent linux this can be diffrent
#vmap unisims_ver $XILINX/verilog/questasim/10.1c/lin64/unisims_ver
#vmap simprims_ver $XILINX/verilog/questasim/10.1c/lin64/simprims_ver 
# ----------------------------------------------------------------

proc vlog_top {} {

    global XILINX
    global BASIL
    
    if { [file exists "work"] == 1} {               
        echo "Deleting old work library ..."
        vdel -all -lib work
    }

    vlib work

    vlog $XILINX/verilog/src/glbl.v

    vlog -lint $BASIL/basil/trunk/device/modules/utils/*.v
    vlog -lint $BASIL/basil/trunk/device/modules/sram_fifo/*.v
    vlog -lint $BASIL/basil/trunk/device/modules/fei4_rx/*.v
    vlog -lint $BASIL/basil/trunk/device/modules/cmd_seq/*.v
    vlog -lint $BASIL/basil/trunk/device/modules/rrp_arbiter/*.v +incdir+$BASIL/basil/trunk/device/modules/rrp_arbiter
    vlog -lint $BASIL/basil/trunk/device/modules/tlu/*.v

    vlog ../src/top.v
    vlog ../src/clk_gen.v

    vlog  -novopt $BASIL/fei4/trunk/models/fei4a/fei4_top.sv +incdir+$BASIL/fei4/trunk/models/fei4a +define+TEST_DC=1
    vlog  +incdir+$BASIL/fei4/trunk/models/fei4a +incdir+$BASIL/basil/trunk/device/modules/tb +incdir+../tb ../tb/top_tb.sv

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
    
    add wave -group {fei4_rx_0 sim:/top_tb/uut/rx_gen[0]/ifei4_rx/i_fei4_rx_core/*}
    add wave -group tlu sim:/top_tb/uut/tlu_controller_module/i_tlu_controller/*

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
    #add wave  -group fei4_aarray_0_0 {sim:/top_tb/fei4_inst/i_FEND_DIGI_ARRAY/genblk1[0]/DC_INST/genblk1[0]/PIX_L/*}
    #add wave -group fei4_c0_r0_m0 {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/latency_mem[0]/mem/*}
    
}


