import array
import struct
import time


class ReadoutUtils(object):
    def __init__(self, device):
        self.device = device
    
    def reser_rx(self):
        while True:
            self.device.WriteExternal(address = 0x8000, data = [0])
            time.sleep(0.1) # TODO: read status value
            status = self.device.ReadExternal(address = 0x8000, size = 8)
            sync = struct.unpack(8*'B', status)[1]
            if sync == 1:
                break
            
    def reset_sram_fifo(self):
        self.device.WriteExternal(address = 0x8100, data = [0])
        time.sleep(0.1) # TODO: read status value
        #print self.device.ReadExternal(address = 0x8100, size = 8)
        
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

