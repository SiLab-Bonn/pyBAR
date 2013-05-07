// controller FSM for TLU communication

`default_nettype none

module tlu_controller_fsm (
    input wire          RESET,
    input wire          CLK,
    
    input wire          CMD_READY,
    output reg          CMD_EXT_START_FLAG,
    input wire          CMD_EXT_START_ENABLE,
    
    input wire          TLU_TRIGGER,
    input wire          TLU_TRIGGER_FLAG,           // external trigger synchronized with CLK
    input wire          TLU_TRIGGER_BUSY,
    output reg          TLU_TRIGGER_DONE,
    
    input wire  [1:0]   TLU_MODE,
    output reg          TLU_BUSY,
    output reg          TLU_ASSERT_VETO,
    output reg          TLU_DEASSERT_VETO,
    output reg          TLU_RECEIVE_DATA_FLAG,
    input wire          TLU_DATA_RECEIVED_FLAG,
    input wire  [7:0]   TLU_TRIGGER_LOW_TIME_OUT,
    output reg          TLU_TRIGGER_ABORT,
    output reg          TLU_TRIGGER_DISABLE,
    
    input wire          FIFO_NEAR_FULL
    
//  output reg  [2:0]   state,
//  output reg  [2:0]   next
);

// FSM
reg     [2:0]   state;
reg     [2:0]   next;
reg     [7:0]   counter_trigger_low_time_out;

// standard state encoding
parameter   [2:0]
    IDLE                             = 4'b0000, // idle state, busy high if SRAM full or measurement pause
    SEND_COMMAND                     = 4'b0001,
    WAIT_FOR_TRIGGER_LOW             = 4'b0010, // busy high, wait for trigger going low
    RECEIVE_TRIGGER_DATA             = 4'b0011, // enable CCK to clock out TLU trigger number
    WAIT_FOR_TLU_DATA                = 4'b0100, // busy high, wait for readout FSM to save TLU trigger number
    WAIT_FOR_CMD                     = 4'b0101, // wait for CMD FSM to be ready
    SEND_TLU_TRIGGER_DONE            = 4'b0110,
    WAIT_FOR_TLU_TRIGGER_BUSY_LOW    = 4'b0111;

// sequential always block, non-blocking assignments
always @ (posedge CLK or posedge RESET)
    begin
        if (RESET)  state <= IDLE; // get D-FF for state
        else        state <= next;
    end

// combinational always block, blocking assignments
always @ (state or TLU_MODE or TLU_DATA_RECEIVED_FLAG or counter_trigger_low_time_out or CMD_READY or CMD_EXT_START_ENABLE or TLU_TRIGGER or TLU_TRIGGER_FLAG or TLU_TRIGGER_BUSY or TLU_TRIGGER_ABORT)
    begin
        case (state)

            IDLE:
            begin
                if ((CMD_READY == 1'b1) && (CMD_EXT_START_ENABLE == 1'b1) && (TLU_TRIGGER_FLAG == 1'b1)) next = SEND_COMMAND; // (CMD_READY == 1'b1) && 
                else next = IDLE;
            end

            SEND_COMMAND:
            begin
                if ((TLU_MODE == 2'b00) || (TLU_MODE == 2'b01)) next = WAIT_FOR_CMD;
                else next = WAIT_FOR_TRIGGER_LOW;
            end

            WAIT_FOR_TRIGGER_LOW:
            begin
                if (TLU_TRIGGER_ABORT == 1'b1) next = IDLE;
                else if ((TLU_MODE == 2'b10) && (TLU_TRIGGER == 1'b0)) next = WAIT_FOR_TLU_DATA; // FIXME: next state WAIT_FOR_TLU_DATA or WAIT_FOR_CMD
                else if ((TLU_MODE == 2'b11) && (TLU_TRIGGER == 1'b0)) next = RECEIVE_TRIGGER_DATA;
                else next = WAIT_FOR_TRIGGER_LOW;
            end

            RECEIVE_TRIGGER_DATA:
            begin
                next = WAIT_FOR_TLU_DATA;
            end

            WAIT_FOR_TLU_DATA:
            begin
                if (TLU_DATA_RECEIVED_FLAG == 1'b1) next = WAIT_FOR_CMD;
                else next = WAIT_FOR_TLU_DATA;
            end

            WAIT_FOR_CMD:
            begin
                if (CMD_READY == 1'b0) next = WAIT_FOR_CMD;
                else next = SEND_TLU_TRIGGER_DONE;
            end
            
            SEND_TLU_TRIGGER_DONE:
            begin
                if (TLU_MODE == 2'b00 || TLU_MODE == 2'b01) next = IDLE; // no busy to be deasserted, state should be back in idle before able to accept new triggers
                else next = WAIT_FOR_TLU_TRIGGER_BUSY_LOW;
            end

            WAIT_FOR_TLU_TRIGGER_BUSY_LOW:
            begin
                if (TLU_TRIGGER_BUSY == 1'b1) next = WAIT_FOR_TLU_TRIGGER_BUSY_LOW;
                else next = IDLE;
            end

            
            // inferring FF
            default:
            begin
                next = IDLE;
            end

        endcase
    end

// sequential always block, non-blocking assignments, registered outputs
always @ (posedge CLK or posedge RESET)
    begin
        
        if (RESET) // get D-FF
            begin
                TLU_RECEIVE_DATA_FLAG <= 1'b0;
                TLU_ASSERT_VETO <= 1'b0;
                TLU_DEASSERT_VETO <= 1'b0;
                TLU_BUSY <= 1'b0;
                counter_trigger_low_time_out <= 8'b0000_0000;
                TLU_TRIGGER_ABORT <= 1'b0;
                TLU_TRIGGER_DONE <= 1'b1;
                CMD_EXT_START_FLAG <= 1'b0;
                TLU_TRIGGER_DISABLE <= 1'b0;
                
            end
        else
            begin

                TLU_RECEIVE_DATA_FLAG <= 1'b0;
                TLU_ASSERT_VETO <= 1'b0;
                TLU_DEASSERT_VETO <= 1'b0;
                TLU_BUSY <= 1'b0;
                counter_trigger_low_time_out <= 8'b0000_0000;
                TLU_TRIGGER_ABORT <= 1'b0;
                TLU_TRIGGER_DONE <= 1'b0;
                CMD_EXT_START_FLAG <= 1'b0;
                TLU_TRIGGER_DISABLE <= 1'b0;

                case (next)

                    IDLE:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        if ((CMD_EXT_START_ENABLE == 1'b0) || (FIFO_NEAR_FULL == 1'b1))
                            begin
                                TLU_ASSERT_VETO <= 1'b1;
                                TLU_DEASSERT_VETO <= 1'b0;
                            end
                        else
                            begin
                                TLU_ASSERT_VETO <= 1'b0;
                                TLU_DEASSERT_VETO <= 1'b1;
                            end
                        //TLU_BUSY <= 1'b0;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        if ((CMD_READY == 1'b1) && (CMD_EXT_START_ENABLE == 1'b1))
                        begin
                            TLU_TRIGGER_DISABLE <= 1'b0;
                            TLU_BUSY <= 1'b0; // FIXME: hack to make first trigger get accepted
                        end
                        else
                        begin
                           TLU_TRIGGER_DISABLE <= 1'b1; // FIXME: hack to make first trigger get accepted
                           TLU_BUSY <= 1'b1;
                        end
                    end
                    
                    SEND_COMMAND:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b1;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end
                    
                    WAIT_FOR_TRIGGER_LOW:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b1;
                        TLU_BUSY <= 1'b1;
                        if (counter_trigger_low_time_out != 8'b1111_1111)
                            counter_trigger_low_time_out <= counter_trigger_low_time_out + 1;
                        else
                            counter_trigger_low_time_out <= counter_trigger_low_time_out;
                        if ((counter_trigger_low_time_out >= TLU_TRIGGER_LOW_TIME_OUT) && (TLU_TRIGGER_LOW_TIME_OUT != 8'b0000_0000))
                            TLU_TRIGGER_ABORT <= 1'b1;
                        else
                            TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end

                    RECEIVE_TRIGGER_DATA:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b1;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end

                    WAIT_FOR_TLU_DATA:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end

                    WAIT_FOR_CMD:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end
                    
                    SEND_TLU_TRIGGER_DONE:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b1;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end

                    WAIT_FOR_TLU_TRIGGER_BUSY_LOW:
                    begin
                        TLU_RECEIVE_DATA_FLAG <= 1'b0;
                        TLU_ASSERT_VETO <= 1'b0;
                        TLU_DEASSERT_VETO <= 1'b0;
                        TLU_BUSY <= 1'b1;
                        counter_trigger_low_time_out <= 8'b0000_0000;
                        TLU_TRIGGER_ABORT <= 1'b0;
                        TLU_TRIGGER_DONE <= 1'b0;
                        CMD_EXT_START_FLAG <= 1'b0;
                        TLU_TRIGGER_DISABLE <= 1'b0;
                    end


                endcase
            end
    end

endmodule