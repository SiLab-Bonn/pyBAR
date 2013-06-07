
vlib work
set XILINX   $env(XILINX)

#vmap unisims_ver $XILINX/verilog/questasim/10.1c/lin64/unisims_ver
#vmap simprims_ver $XILINX/verilog/questasim/10.1c/lin64/simprims_ver 
vlog $XILINX/verilog/src/glbl.v

vlog ../src/fei4_rx/*.v
vlog ../src/*.v
vlog  -novopt ../tb/models/fei4/fei4_top.sv +incdir+../tb/models/fei4 +define+TEST_DC=1
vlog  +incdir+../tb/models/fei4 ../tb/top_tb.sv 

#vlog ../ise/netgen/par/top_timesim.v

proc vsim_top {} {
	vsim -novopt -t 1ps -L unisims_ver  work.top_tb glbl
	

	#vsim -novopt -t 1ps -L unisims_ver  -L simprims_ver work.top_tb glbl 
		
}

proc wave_top {} {
	add wave -group top sim:/top_tb/*
	add wave -group uut sim:/top_tb/uut/*
	add wave -group clkgen sim:/top_tb/uut/iclkgen/*
	add wave -group cmd sim:/top_tb/uut/icmd/*
	add wave -group pa sim:/top_tb/uut/ifei4_rx/ireceiver_logic/irec_sync/iphase_align/*
	add wave -group rec_sync sim:/top_tb/uut/ifei4_rx/ireceiver_logic/irec_sync/*
	add wave -group rec_logic sim:/top_tb/uut/ifei4_rx/ireceiver_logic/*
	add wave -group rx sim:/top_tb/uut/ifei4_rx/*
	add wave -group fei4 sim:/top_tb/fei4_inst/*
	add wave -group fei4_cmd sim:/top_tb/fei4_inst/i_CMD/*
	add wave -group fei4_dob sim:/top_tb/fei4_inst/i_DOB/*
	add wave -group fei4_eochl sim:/top_tb/fei4_inst/i_EOCHL/*
	add wave -group fifo_sram sim:/top_tb/uut/iout_fifo/*
	
	#add wave {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/L1req}
	
	add wave -group fei4_c0_r0 {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/*}
	add wave -group fei4_c0_r0_core {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/*}
	add wave -group fei4_darray {sim:/top_tb/fei4_inst/i_digital_array/*}
	add wave -group fei4_aarray {sim:/top_tb/fei4_inst/i_FEND_DIGI_ARRAY/*}
	add wave  -group fei4_aarray_0_0 {sim:/top_tb/fei4_inst/i_FEND_DIGI_ARRAY/genblk1[0]/DC_INST/genblk1[0]/PIX_L/*}
	add wave -group fei4_c0_r0_m0 {sim:/top_tb/fei4_inst/i_digital_array/genblk1[0]/i_DDC/column_gen[0]/i_region_logic/quad_core/latency_mem[0]/mem/*}
	
}
