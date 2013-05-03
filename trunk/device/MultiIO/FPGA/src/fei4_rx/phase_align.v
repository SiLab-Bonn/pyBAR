

`timescale 1ps/1ps

module phase_align (PLL_RST, DATA_IN, DATA_OUT, IO_CLK, RESET, WCLK, BITSLIP, ERROR, READY, EYE_SIZE, SEARCH_SIZE, lck) ;

parameter DSIZE = 10;
parameter IO_CLK_PERID = 6.25;

input DATA_IN;
output reg [DSIZE-1:0] DATA_OUT;
input IO_CLK, RESET, PLL_RST;
output WCLK, lck;
input BITSLIP; 
output reg ERROR, READY;
output reg [7:0] EYE_SIZE, SEARCH_SIZE;

    wire RST;
    wire PSCLK, PSDONE;
    reg PSEN, PSINCDEC;
    wire [7:0] STATUS;
    wire LOCKED;
    wire CLKFB;
    wire FCLK, FCLK90;

	 assign lck = LOCKED;
    assign RST = RESET || !LOCKED;
    DCM #(
     .CLKDV_DIVIDE(DSIZE), // Divide by: 1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,6.5
     // 7.0,7.5,8.0,9.0,10.0,11.0,12.0,13.0,14.0,15.0 or 16.0
     .CLKFX_DIVIDE(8), // Can be any Integer from 1 to 32
     .CLKFX_MULTIPLY(2), // Can be any Integer from 2 to 32
     .CLKIN_DIVIDE_BY_2("FALSE"), // TRUE/FALSE to enable CLKIN divide by two feature
     .CLKIN_PERIOD(IO_CLK_PERID), // Specify period of input clock
     .CLKOUT_PHASE_SHIFT("VARIABLE"), // Specify phase shift of NONE, FIXED or VARIABLE
     .CLK_FEEDBACK("1X"), // Specify clock feedback of NONE, 1X or 2X
     .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), // SOURCE_SYNCHRONOUS, SYSTEM_SYNCHRONOUS or
     // an Integer from 0 to 15
     .DFS_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for frequency synthesis
     .DLL_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for DLL
     .DUTY_CYCLE_CORRECTION("TRUE"), // Duty cycle correction, TRUE or FALSE
     .FACTORY_JF(16'hC080), // FACTORY JF values
     .PHASE_SHIFT(0), // Amount of fixed phase shift from -255 to 255
     .STARTUP_WAIT("TRUE") // Delay configuration DONE until DCM_SP LOCK, TRUE/FALSE
    ) DCM_inst (
     .DSSEN(1'b0), 
     .CLK0(CLK0), // 0 degree DCM_SP CLK output
     .CLK180(), // 180 degree DCM_SP CLK output
     .CLK270(), // 270 degree DCM_SP CLK output
     .CLK2X(), // 2X DCM_SP CLK output
     .CLK2X180(), // 2X, 180 degree DCM_SP CLK out
     .CLK90(CLK90), // 90 degree DCM_SP CLK output
     .CLKDV(CLKDV), // Divided DCM_SP CLK out (CLKDV_DIVIDE)
     .CLKFX(), // DCM_SP CLK synthesis out (M/D)
     .CLKFX180(), // 180 degree CLK synthesis out
     .LOCKED(LOCKED), // DCM_SP LOCK status output
     .PSDONE(PSDONE), // Dynamic phase adjust done output
     .STATUS(STATUS), // 8-bit DCM_SP status bits output
     .CLKFB(CLKFB), // DCM_SP clock feedback
     .CLKIN(IO_CLK), // Clock input (from IBUFG, BUFG or DCM_SP)
     .PSCLK(PSCLK), // Dynamic phase adjust clock input
     .PSEN(PSEN), // Dynamic phase adjust enable input
     .PSINCDEC(PSINCDEC), // Dynamic phase adjust increment/decrement
     .RST(PLL_RST)//!CLK_160_LOCKED) // DCM_SP asynchronous reset input
    );

 
    assign CLKFB = FCLK;
    //BUFG CLKFX_BUFG_INST (.I(CLKFX), .O(FCLK_DIV4));
    BUFG CLK0_BUFG_INST (.I(CLK0), .O(FCLK));
    BUFG CLK90_BUFG_INST (.I(CLK90), .O(FCLK90));
    BUFG CLKDV_BUFG_INST (.I(CLKDV), .O(WCLK));
    
    wire d0, d1;
    IFDDRRSE  fddrdin (
                 .C0(FCLK),
                 .C1(FCLK90), 
                 .D(DATA_IN),
                 .CE(1'b1),
                 .R(1'b0),
                 .S(1'b0),
                 .Q0(d0),
                 .Q1(d1));

    assign PSCLK = WCLK;

    reg [DSIZE-1:0] shift_reg, shift_reg_c1;
    reg [DSIZE-1:0] shift_reg_dev, shift_reg_c1_dev;
    
    wire fbit_slip;
    reg fbit_slip_ff;
    always@(posedge FCLK)
        fbit_slip_ff <= BITSLIP;
        
    assign fbit_slip = (fbit_slip_ff == 0 && BITSLIP ==1);
    
    always@(posedge FCLK)
        shift_reg <= {shift_reg[DSIZE-2:0], d0};
        
    always@(posedge FCLK)
        shift_reg_c1 <= {shift_reg_c1[DSIZE-2:0], d1};
            
    always@(posedge WCLK)
        shift_reg_dev <= shift_reg;
    
    always@(posedge WCLK)
        shift_reg_c1_dev <= shift_reg_c1;
    
    
    reg [DSIZE-1:0] bitslip_cnt;
    initial bitslip_cnt = 1;
    always@(posedge FCLK)
        if(fbit_slip)
            bitslip_cnt <= {bitslip_cnt[DSIZE-3:0],bitslip_cnt[DSIZE-1:DSIZE-2]};
        else
            bitslip_cnt <= {bitslip_cnt[DSIZE-2:0],bitslip_cnt[DSIZE-1]};
    
    reg [DSIZE-1:0] fdataout;
    always@(posedge FCLK)
        if(bitslip_cnt[0])
            fdataout <= shift_reg;
     
    always@(posedge WCLK)
            DATA_OUT <= fdataout;
    
    wire JITTER_PHASE;
    assign JITTER_PHASE = (shift_reg_dev != shift_reg_c1_dev);
    
    reg CALIB_STOP;
    
    wire POVERLOAD;
    assign POVERLOAD = STATUS[0];
    
    localparam START = 0, SEARCH_BACK_DECIDE = 1, SEARCH_BACK = 2, 
	 SEARCH_FORWARD = 3, SEARCH_BACK_WAIT = 4, SEARCH_FORWARD_WAIT = 5,
	 MEASURE = 6 , MEASURE_WAIT = 7, CALIB = 8, CALIB_WAIT = 9, 
	 FINISH = 10, ERROR_STATE = 11, SEARCH_FORWARD_DECIDE = 12, MEASURE_DECIDE = 13;
	 
    reg [3:0] state, next_state;
    reg [8:0] measeure_cnt, calib_pos, calib_cnt, start_cnt, jit_cnt, search_cnt;
    
    always@(posedge WCLK or posedge RST)
        if(RST)
            state <= START;
        else
            state <= next_state;


    always@(*) begin
       next_state = state;
        
        case(state)
            START: 
					if(start_cnt>32) begin
							if(jit_cnt == 0)
								next_state = SEARCH_BACK;
							else
								next_state = SEARCH_FORWARD;
					end
            SEARCH_BACK:
                    if(POVERLOAD)
                        next_state = ERROR_STATE;
                    else
                        next_state = SEARCH_BACK_WAIT;
            SEARCH_BACK_WAIT:
						if(PSDONE)
								next_state = SEARCH_BACK_DECIDE;
				SEARCH_BACK_DECIDE:
						if(start_cnt>32) begin
							if(jit_cnt != 0)
                        next_state = MEASURE;
                     else
                        next_state = SEARCH_BACK;
						end
				
            SEARCH_FORWARD:
                    if(POVERLOAD)
                        next_state = ERROR_STATE;
                    else
                        next_state = SEARCH_FORWARD_WAIT;
            SEARCH_FORWARD_WAIT:
                if(PSDONE)
							next_state = SEARCH_FORWARD_DECIDE;
				SEARCH_FORWARD_DECIDE:
						if(start_cnt>32) begin
							if(jit_cnt == 0)
                        next_state = MEASURE;
                     else
                        next_state = SEARCH_FORWARD;
						end
            MEASURE:
                if(POVERLOAD)
                        next_state = CALIB; //next_state = ERROR_STATE; !!!!very bad hack!!!!
                else
                    next_state = MEASURE_WAIT;
            MEASURE_WAIT:
                if(PSDONE)
                    next_state = MEASURE_DECIDE;
				MEASURE_DECIDE:
					 if(measeure_cnt < 8) //add some time 
								next_state = MEASURE;	
					  else begin
							if(start_cnt>32) begin
								if(jit_cnt == 0)
									next_state = MEASURE;
								else
									next_state = CALIB;
							end
						end
            CALIB:
                    next_state = CALIB_WAIT;
            CALIB_WAIT:
                if(PSDONE)
                    if(CALIB_STOP)
                        next_state = FINISH;
                    else
                        next_state = CALIB;
            FINISH:
                next_state = FINISH;
            ERROR_STATE:
                next_state = ERROR_STATE;
        default : next_state = ERROR_STATE;

        endcase
    end
    
    always@(posedge WCLK)
        if(RST)
            measeure_cnt <= 0;
        else if(state == MEASURE)
            measeure_cnt <= measeure_cnt + 1;
        
    always@(posedge WCLK)
        if(RST)
            calib_cnt <= 0;
        else if(state == CALIB)
            calib_cnt <= calib_cnt + 1;
				
	  always@(posedge WCLK)
        if(RST || state != next_state)
            start_cnt <= 0;
        else
            start_cnt <= start_cnt + 1;

	  always@(posedge WCLK)
		if(RST || state != next_state)
			jit_cnt <= 0;
		else if(JITTER_PHASE)
			jit_cnt <= jit_cnt + 1;

    always@(posedge WCLK)
        if(RST)
            search_cnt <= 0;
        else if(state == SEARCH_BACK || state == SEARCH_FORWARD)
            search_cnt <= search_cnt + 1;
				
    
    always@(*) begin
        PSEN = 0;
        PSINCDEC = 0;
        
        if(state == SEARCH_BACK || state == SEARCH_FORWARD || state == MEASURE || state == CALIB)
            PSEN = 1;
        
        if(state == SEARCH_FORWARD || state == MEASURE)
            PSINCDEC = 1;
        
        calib_pos = (measeure_cnt -1 + 64)/2;
        CALIB_STOP = ((calib_pos-64) == calib_cnt);
        
        ERROR =  (state == ERROR_STATE);
        READY =  (state == FINISH);
        EYE_SIZE = (measeure_cnt -1 + 64);
		  SEARCH_SIZE = search_cnt;
    end
	 
	 
	 `ifdef SYNTHESIS_NOT
    wire [35:0] control_bus;
    chipscope_icon ichipscope_icon
    (
        .CONTROL0(control_bus)
    ); 

    
    chipscope_ila ichipscope_ila 
    (
        .CONTROL(control_bus),
        .CLK(WCLK), 
		  .TRIG0({JITTER_PHASE, READY, BITSLIP, PSEN, PSINCDEC, POVERLOAD, PSDONE, shift_reg_c1_dev , shift_reg_dev, state, RST})
			
    ); 
    `endif
	 
    
endmodule