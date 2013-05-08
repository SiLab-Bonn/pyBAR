module tlu_serial_to_parallel_fsm (
    input wire          RESET,
    input wire          CLK,
    
    input wire  [4:0]   TLU_TRIGGER_CLOCK_CYCLES,
    input wire  [3:0]   TLU_TRIGGER_DATA_DELAY,
    input wire          TLU_TRIGGER_DATA_MSB_FIRST,

    input wire          TLU_TRIGGER,                // external trigger synchronized with CLK
    input wire          TLU_RECEIVE_DATA_FLAG,
    output reg          TLU_CLOCK_ENABLE,
    output reg          TLU_DATA_RECEIVED_FLAG,

    output reg  [31:0]  TLU_DATA,
    output reg          TLU_DATA_SAVE_SIGNAL,
    output reg          TLU_DATA_SAVE_FLAG,
    input wire          TLU_DATA_SAVED_FLAG

);

integer n; // for for-loop (reversing TLU data)

reg     [31:0]      tlu_data_sr;

// shift register, serial to parallel, 32 FF
always @ (posedge CLK)
begin
    tlu_data_sr[31:0] <= {tlu_data_sr[30:0], TLU_TRIGGER};
end

// FSM
reg [2:0] state;
reg [2:0] next;

reg     [4:0]   counter_tlu_clock;
reg     [3:0]   counter_sr_wait_cycles;
reg     [31:0]  tlu_data_sr_reversed;

parameter   [2:0]
    IDLE                        = 3'b000, // idle state
    SEND_TLU_CLOCK              = 3'b001, // send TLU clock
    WAIT_BEFORE_LATCH           = 3'b010, // wait cycles before data getting latched
    LATCH_DATA                  = 3'b011, // latch 32-bit register
    SEND_TLU_DATA               = 3'b100, // send TLU data in advance
    SEND_DATA_SAVE              = 3'b101, // send data save signal/flag
    WAIT_FOR_SAVE               = 3'b110, // wait for TLU trigger number saved
    SEND_TLU_DATA_RECEIVED      = 3'b111; // send ready signal

always @ (posedge CLK or posedge RESET)
    begin
        if (RESET == 1'b1)  state <= IDLE; // get D-FF for state
        else                state <= next;
    end

always @ (state or TLU_RECEIVE_DATA_FLAG or TLU_DATA_SAVED_FLAG or TLU_TRIGGER_CLOCK_CYCLES or counter_tlu_clock or counter_sr_wait_cycles or TLU_TRIGGER_DATA_DELAY)
    begin
        case (state)
            IDLE:
            begin
                if (TLU_RECEIVE_DATA_FLAG == 1'b1) next = SEND_TLU_CLOCK;
                else next = IDLE;
            end

            SEND_TLU_CLOCK:
            begin
                if (counter_tlu_clock == TLU_TRIGGER_CLOCK_CYCLES) next = WAIT_BEFORE_LATCH;
                else next = SEND_TLU_CLOCK;
            end

            WAIT_BEFORE_LATCH:
            begin
                if (counter_sr_wait_cycles == TLU_TRIGGER_DATA_DELAY + 4) next = LATCH_DATA; // 4 clock cycles is minimum delay
                else next = WAIT_BEFORE_LATCH;
            end

            LATCH_DATA:
            begin
                next = SEND_TLU_DATA;
            end
            
            SEND_TLU_DATA:
            begin
                next = SEND_DATA_SAVE;
            end
            
            SEND_DATA_SAVE:
            begin
                next = WAIT_FOR_SAVE;
            end

            WAIT_FOR_SAVE:
            begin
                if (TLU_DATA_SAVED_FLAG == 1'b1) next = SEND_TLU_DATA_RECEIVED;
                else next = WAIT_FOR_SAVE;
            end

            SEND_TLU_DATA_RECEIVED:
            begin
                next = IDLE;
            end

            default:
            begin
                next = IDLE;
            end
        endcase
end

always @ (posedge CLK or posedge RESET)
    begin
        
        if (RESET) // get D-FF
            begin
                TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                TLU_DATA_SAVE_SIGNAL <= 1'b0;
                TLU_DATA_SAVE_FLAG <= 1'b0;
                TLU_CLOCK_ENABLE <= 1'b0;
                counter_tlu_clock <= 5'b0_0000;
                counter_sr_wait_cycles <= 8'b0000_0000;
                TLU_DATA_RECEIVED_FLAG <= 1'b0;
            end
        else
            begin

                TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                TLU_DATA_SAVE_SIGNAL <= 1'b0;
                TLU_DATA_SAVE_FLAG <= 1'b0;
                TLU_CLOCK_ENABLE <= 1'b0;
                counter_tlu_clock <= 5'b0_0000;
                counter_sr_wait_cycles <= 8'b0000_0000;
                TLU_DATA_RECEIVED_FLAG <= 1'b0;

                case (next)
                    IDLE:
                    begin
                        TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end

                    SEND_TLU_CLOCK:
                    begin
                        TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b1;
                        counter_tlu_clock <= counter_tlu_clock + 1;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end

                    WAIT_BEFORE_LATCH:
                    begin
                        TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        if (counter_sr_wait_cycles != 4'b1111)
                            counter_sr_wait_cycles <= counter_sr_wait_cycles + 1;
                        else
                            counter_sr_wait_cycles <= counter_sr_wait_cycles;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end

                    LATCH_DATA:
                    begin
                        TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        if (TLU_TRIGGER_DATA_MSB_FIRST == 1'b1)
                                tlu_data_sr_reversed <= tlu_data_sr[31:0];
                        else
                        begin
                            for ( n=0 ; n < 32 ; n=n+1 )
                            begin
                                tlu_data_sr_reversed[n] <= tlu_data_sr[31-n]; // reverse bit order
                            end
                            //tlu_data_sr_reversed <= {tlu_data_sr[0], tlu_data_sr[1], tlu_data_sr[2], tlu_data_sr[3], tlu_data_sr[4], tlu_data_sr[5], tlu_data_sr[6], tlu_data_sr[7], tlu_data_sr[8], tlu_data_sr[9], tlu_data_sr[10], tlu_data_sr[11], tlu_data_sr[12], tlu_data_sr[13], tlu_data_sr[14], tlu_data_sr[15], tlu_data_sr[16], tlu_data_sr[17], tlu_data_sr[18], tlu_data_sr[19], tlu_data_sr[20], tlu_data_sr[21], tlu_data_sr[22], tlu_data_sr[23], tlu_data_sr[24], tlu_data_sr[25], tlu_data_sr[26], tlu_data_sr[27], tlu_data_sr[28], tlu_data_sr[29], tlu_data_sr[30], tlu_data_sr[31]};
                        end
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end

                    SEND_TLU_DATA:
                    begin
                        if (TLU_TRIGGER_CLOCK_CYCLES == 5'b0_0000)
                            TLU_DATA <= tlu_data_sr_reversed;
                        else
                        begin
                            for ( n=0 ; n < 32 ; n=n+1 )
                            begin
                                if (n >= TLU_TRIGGER_CLOCK_CYCLES-1)
                                    TLU_DATA[n] <= 1'b0;
                                else
                                    TLU_DATA[n] <= tlu_data_sr_reversed[32-TLU_TRIGGER_CLOCK_CYCLES+1+n];
                            end
                        end
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end
                    
                    SEND_DATA_SAVE:
                    begin
                        TLU_DATA <= TLU_DATA;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b1;
                        TLU_DATA_SAVE_FLAG <= 1'b1;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end

                    WAIT_FOR_SAVE:
                    begin
                        TLU_DATA <= TLU_DATA;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b1;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b0;
                    end
                    
                    SEND_TLU_DATA_RECEIVED:
                    begin
                        TLU_DATA <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        tlu_data_sr_reversed <= 32'b0000_0000_0000_0000_0000_0000_0000_0000;
                        TLU_DATA_SAVE_SIGNAL <= 1'b0;
                        TLU_DATA_SAVE_FLAG <= 1'b0;
                        TLU_CLOCK_ENABLE <= 1'b0;
                        counter_tlu_clock <= 5'b0_0000;
                        counter_sr_wait_cycles <= 8'b0000_0000;
                        TLU_DATA_RECEIVED_FLAG <= 1'b1;
                    end
                
                endcase
            end
    end

endmodule
