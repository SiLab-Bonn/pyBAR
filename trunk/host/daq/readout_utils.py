import struct
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


trigger_modes = {
    0: 'external trigger',
    1: 'TLU no handshake',
    2: 'TLU simple handshake',
    3: 'TLU trigger data handshake'
}


class ReadoutUtils(object):
    def __init__(self, device):
        self.device = device

    def configure_command_fsm(self, enable_ext_trigger=False, neg_edge=False, diable_clock=False, disable_command_trigger=False):
        '''Setting up command FSM to receive external triggers.

        Parameters
        ----------
        enable_ext_trigger : bool
            Enabling external trigger and TLU trigger.
        neg_edge : bool
            Sending data on negative edge of FE clock.
        diable_clock : bool
            Disabling FE clock.
        disable_command_trigger : bool
            Disabling command trigger. Command trigger sends pulse to LEMO TX1 when sending command to FE. Sending pulses over LEMO TX1 only when enable_ext_trigger is set to false.
        '''
        logging.info('External trigger %s' % ('enabled' if enable_ext_trigger else 'disabled'))
#         array = self.device.ReadExternal(address=0 + 2, size=1)  # get stored register value
#         reg = struct.unpack('B', array)[0]
        reg = 0
        if enable_ext_trigger:
            reg |= 0x01
        else:
            reg &= ~0x01
        if neg_edge:
            reg |= 0x02
        else:
            reg &= ~0x02
        if diable_clock:
            reg |= 0x04
        else:
            reg &= ~0x04
        if disable_command_trigger:
            reg |= 0x08
        else:
            reg &= ~0x08
        self.device.WriteExternal(address=0 + 2, data=[reg])  # overwriting register

    def configure_trigger_fsm(self, mode=0, trigger_data_msb_first=False, disable_veto=False, trigger_data_delay=0, trigger_clock_cycles=16, enable_reset=False, invert_lemo_trigger_input=False, trigger_low_timeout=0):
        '''Setting up external trigger mode and TLU trigger FSM.

        Parameters
        ----------
        mode : string
            TLU handshake mode. External trigger has to be enabled in command FSM. From 0 to 3.
            0: External trigger (LEMO RX0 only, TLU port disabled (TLU port/RJ45)).
            1: TLU no handshake (automatic detection of TLU connection (TLU port/RJ45)).
            2: TLU simple handshake (automatic detection of TLU connection (TLU port/RJ45)).
            3: TLU trigger data handshake (automatic detection of TLU connection (TLU port/RJ45)).
        trigger_data_msb_first : bool
            Setting endianness of TLU trigger data.
        disable_veto : bool
            Disabling TLU veto support.
        trigger_data_delay : int
            Addition wait cycles before latching TLU trigger data. From 0 to 15.
        trigger_clock_cycles : int
            Number of clock cycles sent to TLU to clock out TLU trigger data. The number of clock cycles is usually (bit length of TLU trigger data + 1). From 0 to 31.
        enable_reset : bool
            Enable resetting of internal trigger counter when TLU asserts reset signal.
        invert_lemo_trigger_input : bool
            Enable inverting of LEMO RX0 trigger input.
        trigger_low_timeout : int
            Enabling timeout for waiting for de-asserting TLU trigger signal. From 0 to 255.
        '''
        logging.info('Trigger mode: %s' % trigger_modes[mode])
#         array = self.device.ReadExternal(address = 0x8200+1, size = 3)  # get stored register value
#         reg = struct.unpack(4*'B', array)
        reg_1 = (mode & 0x03)
        if trigger_data_msb_first:
            reg_1 |= 0x04
        else:
            reg_1 &= ~0x04
        if disable_veto:
            reg_1 |= 0x08
        else:
            reg_1 &= ~0x08
        reg_1 = ((trigger_data_delay & 0x0f) << 4) | (reg_1 & 0x0f)
        reg_2 = (trigger_clock_cycles & 0x1F)  # 0 = 32 clock cycles
        if enable_reset:
            reg_2 |= 0x20
        else:
            reg_2 &= ~0x20
        if invert_lemo_trigger_input:
            reg_2 |= 0x40
        else:
            reg_2 &= ~0x40
        reg_3 = trigger_low_timeout
        self.device.WriteExternal(address=0x8200 + 1, data=[reg_1, reg_2, reg_3])  # overwriting registers

    def get_tlu_trigger_number(self):
        '''Reading most recent TLU trigger data/number.
        '''
        trigger_number_array = self.device.ReadExternal(address=0x8200 + 4, size=4)
        return struct.unpack('I', trigger_number_array)[0]

    def get_trigger_number(self):
        '''Reading internal trigger counter.
        '''
        trigger_number_array = self.device.ReadExternal(address=0x8200 + 8, size=4)
        return struct.unpack('I', trigger_number_array)[0]
