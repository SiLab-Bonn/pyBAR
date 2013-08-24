#import array
import struct
import time


class ReadoutUtils(object):
    def __init__(self, device):
        self.device = device
        
    def set_ext_cmd_start(self, enable, neg_edge = False):
        array = self.device.ReadExternal(address = 0+2, size = 1)
        reg = struct.unpack('B', array)[0]
        if enable:
            reg |= 0x01
        else:
            reg &= ~0x01
        if neg_edge:
            reg |= 0x08
        else:
            reg &= ~0x08
        self.device.WriteExternal(address = 0+2, data = [reg])
        
        
    def set_tlu_mode(self, mode, trigger_data_msb_first = False, disable_veto = False, enable_reset = False, trigger_data_delay = 0, tlu_trigger_clock_cycles = 16, tlu_trigger_low_timeout = 0):
        #array = self.device.ReadExternal(address = 0x8200+1, size = 3)
        #reg = struct.unpack(4*'B', array)
        reg_1 = (mode&0x03)
        if trigger_data_msb_first:
            reg_1 |= 0x04
        else:
            reg_1 &= ~0x04
        if disable_veto:
            reg_1 |= 0x08
        else:
            reg_1 &= ~0x08
        reg_1 = ((trigger_data_delay&0x0f)<<4)|(reg_1&0x0f)
        reg_2 = (tlu_trigger_clock_cycles&0x1F) # 0 = 32 clock cycles
        if enable_reset:
            reg_2 |= 0x20
        else:
            reg_2 &= ~0x20
        reg_2_spare = 0
        reg_2 = ((reg_2_spare&0x03)<<6)|(reg_2&0x03F)
        reg_3 = tlu_trigger_low_timeout
        self.device.WriteExternal(address = 0x8200+1, data = [reg_1, reg_2, reg_3])
        #print self.device.ReadExternal(address = 0x8200+1, size = 3)
        
    def get_tlu_trigger_number(self):
        trigger_number_array = self.device.ReadExternal(address = 0x8200+4, size = 4)
        return struct.unpack('I', trigger_number_array)[0]
    
    def get_trigger_number(self):
        trigger_number_array = self.device.ReadExternal(address = 0x8200+8, size = 4)
        return struct.unpack('I', trigger_number_array)[0]
        
