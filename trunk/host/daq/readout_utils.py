import struct
import logging
import array
import numpy as np
import readout

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


cmd_modes = {
    0: 'positive edge',
    1: 'negative edge',
    2: 'Manchester Code IEEE 802.3',
    3: 'Manchester Code G.E. Thomas'
}


trigger_modes = {
    0: 'external trigger',
    1: 'TLU no handshake',
    2: 'TLU simple handshake',
    3: 'TLU trigger data handshake'
}


class ReadoutUtils(object):
    def __init__(self, device):
        self.device = device
        self.rx_base_address = dict([(idx, addr) for idx, addr in enumerate(range(0x8600, 0x8200, -0x0100))])

    def configure_rx_fsm(self, channels=None, invert_rx_data=False, **kwargs):
        '''Setting up RX FSM.

        Parameters
        ----------
        channels : list, tuple
            List of readout channels to which the setting is applied.
        invert_rx_data : bool
            Enables inverting RX data. This can be used to compensate swapped n and p LVDS signal lines.
        '''
        if invert_rx_data:
            logging.info('Inverting of RX data enabled')
        reg = 0
        if invert_rx_data:
            reg |= 0x02
        else:
            reg &= ~0x02
        if channels == None:
            channels = self.rx_base_address.iterkeys()
        filter(lambda i: self.device.WriteExternal(address=self.rx_base_address[i] + 2, data=[reg]), channels)  # overwriting selected register

    def configure_command_fsm(self, enable_ext_trigger=False, cmd_mode=0, diable_clock=False, disable_command_trigger=False, **kwargs):
        '''Setting up command FSM to receive external triggers.

        Parameters
        ----------
        enable_ext_trigger : bool
            Enabling external trigger and TLU trigger.
        cmd_mode : bool
            Changing CMD output mode. From 0 to 3.
            0: positive edge (default)
            1: negative edge
            2: Manchester Code IEEE 802.3 (for capacitively coupled Din)
            3: Manchester Code G.E. Thomas
        diable_clock : bool
            Disabling FE clock.
        disable_command_trigger : bool
            Disabling command trigger. Command trigger sends pulse to LEMO TX1 when sending command to FE. Sending pulses over LEMO TX1 only when enable_ext_trigger is set to false.
        '''
        if cmd_mode != 0:
            logging.info('Command mode: %s' % cmd_modes[cmd_mode])
        logging.info('External trigger %s' % ('enabled' if enable_ext_trigger else 'disabled'))
#         array = self.device.ReadExternal(address=0 + 2, size=1)  # get stored register value
#         reg = struct.unpack('B', array)[0]
        reg = 0
        if enable_ext_trigger:
            reg |= 0x01
        else:
            reg &= ~0x01
        reg = ((cmd_mode & 0x03) << 1) | (reg & 0xf9)
        if diable_clock:
            reg |= 0x08
        else:
            reg &= ~0x08
        if disable_command_trigger:
            reg |= 0x10
        else:
            reg &= ~0x10
        self.device.WriteExternal(address=0 + 2, data=[reg])  # overwriting register

    def configure_trigger_fsm(self, trigger_mode=0, trigger_data_msb_first=False, disable_veto=False, trigger_data_delay=0, trigger_clock_cycles=16, enable_reset=False, invert_lemo_trigger_input=False, write_tlu_timestamp=False, trigger_low_timeout=0, reset_trigger_counter=False, **kwargs):
        '''Setting up external trigger mode and TLU trigger FSM.

        Parameters
        ----------
        trigger_mode : int
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
            Number of clock cycles sent to TLU to clock out TLU trigger data (only in TLU trigger data handshake mode). The number of clock cycles is usually (bit length of TLU trigger data + 1). From 0 to 31 (0 = 32 clock cycles).
        enable_reset : bool
            Enable resetting of internal trigger counter when TLU asserts reset signal.
        invert_lemo_trigger_input : bool
            Enable inverting of LEMO RX0 trigger input.
        write_tlu_timestamp : bool
            Writing time stamp to SRAM every trigger (not available in TLU trigger data handshake mode).
        trigger_low_timeout : int
            Enabling timeout for waiting for de-asserting TLU trigger signal. From 0 to 255.
        reset_trigger_counter : bool
            Reset trigger counter to zero.
        '''
        logging.info('Trigger mode: %s' % trigger_modes[trigger_mode])
#         array = self.device.ReadExternal(address = 0x8200+1, size = 3)  # get stored register value
#         reg = struct.unpack(4*'B', array)
        reg_1 = (trigger_mode & 0x03)
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
        if write_tlu_timestamp:
            reg_2 |= 0x80
        else:
            reg_2 &= ~0x80
        reg_3 = trigger_low_timeout
        if reset_trigger_counter:
            self.set_trigger_number(value=0)
        self.device.WriteExternal(address=0x8200 + 1, data=[reg_1, reg_2, reg_3])  # overwriting registers
#         if not force_use_rj45:
#             array = self.device.ReadExternal(address=0x8200 + 2, size=1)  # get stored register value
#             reg = struct.unpack('B', array)
#             if reg[0] & 0x80:
#                 logging.info('TLU detected on RJ45 port')
#         else:
#             logging.info('Using RJ45 port for triggering')

    def configure_tdc_fsm(self, enable_tdc=False, enable_ext_tdc=False, enable_tdc_arming=False, write_tdc_timestamp=False, **kwargs):
        '''Setting up TDC (time-to-digital converter) FSM.

        Parameters
        ----------
        enable_tdc : bool
            Enables TDC. TDC will measure signal at RX0 (LEMO trigger input).
        enable_ext_tdc : bool
            Enables TDC when external signal is applied to xxx port. TDC will measure signal at RX0 (LEMO trigger input).
        enable_tdc_arming : bool
            Enables arming of TDC. TDC will only measure a signal when triggered (command is sent out).
        write_tdc_timestamp : bool
            Writes 16-bit time stamp (40MHz) instead of TDC counter.
        '''
#         array = self.device.ReadExternal(address=0x8700 + 1, size=1)  # get stored register value
#         reg = struct.unpack('B', array)[0]
        reg = 0
        if enable_tdc:
            reg |= 0x01
        else:
            reg &= ~0x01
        if enable_ext_tdc:
            reg |= 0x02
        else:
            reg &= ~0x02
        if enable_tdc_arming:
            reg |= 0x04
        else:
            reg &= ~0x04
        if write_tdc_timestamp:
            reg |= 0x08
        else:
            reg &= ~0x08
        self.device.WriteExternal(address=0x8700 + 1, data=[reg])

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

    def set_trigger_number(self, value=0):
        '''Reading internal trigger counter.
        '''
        trigger_number = array.array('B', struct.pack('I', value))
        self.device.WriteExternal(address=0x8200 + 8, data=trigger_number)
        read_value = self.get_trigger_number()
        if read_value != value:
            logging.warning('Trigger counter is not %d (read %d)' % (value, read_value))


def interpret_pixel_data(self, data, dc, pixel_array):
    '''Takes the pixel raw data and interprets them. This includes consistency checks and pixel/data matching.
    The data has to come from one double column only but can have more than one pixel bit (e.g. TDAC = 5 bit)

    Parameters
    ----------
    data : numpy.ndarray
        The raw data words
    dc : int
        The double column where the data is from.
    pixel_array : numpy.ma.ndarray
        The masked numpy.ndarrays to be filled. The masked is set to zero for pixels with valid data.
    '''

    # data validity cut, VR has to follow an AR
    index_value = np.where(readout.is_address_record(data))[0] + 1  # assume value record follows address record
    index_value = index_value[readout.is_value_record(data[index_value])]  # delete all non value records
    index_address = index_value - 1  # calculate address record indices that are followed by an value record

    # create the pixel address/value arrays
    address = readout.get_address_record_address(data[index_address])
    value = readout.get_value_record(data[index_address + 1])

    # split array for each bit in pixel data, split is done on decreasing address values
    address_split = np.array_split(address, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)
    value_split = np.array_split(value, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)

    mask = np.empty_like(pixel_array.mask)  # BUG in numpy: pixel_array is demasked
    mask[:] = len(address_split)

    for bit, (bit_address, bit_value) in enumerate(zip(address_split, value_split)):  # loop over all bits of the pixel data
        # error output, pixel data is often corrupt for FE-I4A
        if len(bit_address) != 42:
            logging.warning('Pixel data not complete')
        if (bit_address[bit_address > 672] != 0):
            RuntimeError('Pixel data corrupt')
        # set pixel that occurred in the data stream
        pixel = []
        for i in bit_address:
            pixel.extend(range(i - 15, i + 1))
        pixel = np.array(pixel)

        # create bit set array
        value_new = bit_value.view(np.uint8)  # interpret 32 bit numpy array as uint8 to be able to use bit unpacking; byte unpacking is not supported yet
        value_new = np.invert(value_new)  # read back values are inverted
        value_new = np.insert(value_new[::4], np.arange(len(value_new[1::4])), value_new[1::4])  # delete 0 padding
        value_bit = np.unpackbits(value_new, axis=0)

        if len(address_split) == 5:  # detect TDAC data, here the bit order is flipped
            bit_set = len(address_split) - bit - 1
        else:
            bit_set = bit

        pixel_array.data[dc * 2, pixel[pixel < 336]] = np.bitwise_or(pixel_array.data[dc * 2, pixel[pixel < 336]], np.left_shift(value_bit[pixel < 336], bit_set))
        pixel_array.data[dc * 2 + 1, pixel[pixel >= 336] - 336] = np.bitwise_or(pixel_array.data[dc * 2 + 1, pixel[pixel >= 336] - 336], np.left_shift(value_bit[pixel >= 336], bit_set))

        mask[dc * 2, pixel[pixel < 336]] = mask[dc * 2, pixel[pixel < 336]] - 1
        mask[dc * 2 + 1, pixel[pixel >= 336] - 336] = mask[dc * 2 + 1, pixel[pixel >= 336] - 336] - 1

    pixel_array.mask[np.equal(mask, 0)] = False  # mask pixel without data
