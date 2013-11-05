import struct
import array
import math
import time
import numpy as np
import re

from bitstring import BitArray
#import BitVector

from output import FEI4Record
from utils.utils import bitvector_to_array


class FEI4RegisterUtils(object):
    def __init__(self, device, readout_utils, register):
        self.device = device
        self.readout_utils = readout_utils
        self.register = register
        
    def send_commands(self, commands = None, repeat = 1, repeat_all = 1, wait_for_cmd = False, command_bit_length = None):
        if repeat != 1:
            self.set_hardware_repeat(repeat)
        for _ in range(repeat_all):
            if commands == None:
                self.device.WriteExternal(address = 0+1, data = [0])
                self.wait_for_command(wait_for_cmd = wait_for_cmd, command_bit_length = command_bit_length, repeat = repeat)
            else:
                for command in commands:
                    command_bit_length = self.set_command(command)
                    self.device.WriteExternal(address = 0+1, data = [0])
                    self.wait_for_command(wait_for_cmd = wait_for_cmd, command_bit_length = command_bit_length, repeat = repeat)
        # set back to default value of 1
        if repeat != 1:
            self.set_hardware_repeat()

    def send_command(self, command = None, repeat = 1, wait_for_cmd = False, command_bit_length = None):
        if repeat != 1:
            self.set_hardware_repeat(repeat)
        if command != None:
            command_bit_length = self.set_command(command)
        # sending command
        self.device.WriteExternal(address = 0+1, data = [0])
        self.wait_for_command(wait_for_cmd = wait_for_cmd, command_bit_length = command_bit_length, repeat = repeat)
        # set back to default value of 1
        if repeat != 1:
            self.set_hardware_repeat()
    
    def set_command(self, command):
#        if not isinstance(command, BitVector.BitVector):
#            raise TypeError()
        # set command bit length
        command_bit_length = command.length()
        bit_length_array = array.array('B', struct.pack('H', command_bit_length))
        self.device.WriteExternal(address = 0+3, data = bit_length_array)
        # set command
        byte_array = bitvector_to_array(command)
        self.device.WriteExternal(address = 0+8, data = byte_array)
        return command_bit_length
    
    def set_hardware_repeat(self, repeat = 1):
        repeat_array = array.array('B', struct.pack('H', repeat))
        self.device.WriteExternal(address = 0+5, data = repeat_array)
    
    def wait_for_command(self, wait_for_cmd = False, command_bit_length = None, repeat = 1):
        #print self.device.ReadExternal(address = 0+1, size = 1)[0]
        if command_bit_length and wait_for_cmd:
            #print 'sleeping'
            time.sleep((command_bit_length+500)*0.000000025*repeat) # TODO: optimize wait time
        if wait_for_cmd:
            while not self.device.ReadExternal(address = 0+1, size = 1)[0]&0x01:
                #print 'waiting'
                pass
  
    def global_reset(self):
        '''FEI4 Global Reset
        
        Special function to do a global reset on FEI4. Sequence of commands has to be like this, otherwise FEI4 will be left in weird state.  
        '''
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        #vthin_altfine, vthin_altcoarse = self.register.get_global_register_value("Vthin_AltFine"), self.register.get_global_register_value("Vthin_AltCoarse")
        #self.register.set_global_register_value("Vthin_AltFine", 255)
        #self.register.set_global_register_value("Vthin_AltCoarse", 255)
        #commands.extend(self.register.get_commands("wrregister", name = ["Vthin_AltFine", "Vthin_AltCoarse"]))
        commands.extend(self.register.get_commands("globalreset"))
        self.send_commands(commands)
        time.sleep(0.1)
        commands[:] = []
        commands.extend(self.register.get_commands("confmode"))
        #self.register.set_global_register_value("Vthin_AltFine", vthin_altfine)
        #self.register.set_global_register_value("Vthin_AltCoarse", vthin_altcoarse)
        #commands.extend(self.register.get_commands("wrregister", name = ["Vthin_AltFine", "Vthin_AltCoarse"]))
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        
    def configure_all(self, same_mask_for_all_dc=False, do_global_rest=False):
        if do_global_rest:
            self.global_reset()
        self.configure_global()
        self.configure_pixel(same_mask_for_all_dc = same_mask_for_all_dc)
        
    def configure_global(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrregister", readonly=False))
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        
    def configure_pixel(self, same_mask_for_all_dc = False):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = same_mask_for_all_dc, name = ["Imon", "Enable", "c_high", "c_low", "TDAC", "FDAC"]))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = same_mask_for_all_dc, name = ["EnableDigInj"])) # write EnableDigInj last
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        
    def read_service_records(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.send_commands(commands)
        self.readout_utils.reset_sram_fifo()
        commands = []
        self.register.set_global_register_value('ReadErrorReq', 1)
        commands.extend(self.register.get_commands("wrregister", name = ['ReadErrorReq']))
        commands.extend(self.register.get_commands("globalpulse", width = 0))
        self.register.set_global_register_value('ReadErrorReq', 0)
        commands.extend(self.register.get_commands("wrregister", name = ['ReadErrorReq']))
        self.send_commands(commands)
        
        retfifo = self.device.ReadExternal(address = 0x8100, size = 8)
        size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
        fifo_data = self.device.FastBlockRead(4*size/2)
        data = struct.unpack('>'+size/2*'I', fifo_data)
        
        read_records = []
        for word in data:
            fei4_data = FEI4Record(word, self.register.chip_flavor)
            if fei4_data == 'SR':
                read_records.append(fei4_data)
                    
        commands = []
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        return read_records
        
    def read_chip_sn(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.send_commands(commands)
        self.readout_utils.reset_sram_fifo()
        if self.register.is_chip_flavor('fei4b'):
            commands = []
            self.register.set_global_register_value('Efuse_Sense', 1)
            commands.extend(self.register.get_commands("wrregister", name = ['Efuse_Sense']))
            commands.extend(self.register.get_commands("globalpulse", width = 0))
            self.register.set_global_register_value('Efuse_Sense', 0)
            commands.extend(self.register.get_commands("wrregister", name = ['Efuse_Sense']))
            self.send_commands(commands)
        commands = []
        self.register.set_global_register_value('Conf_AddrEnable', 1)
        commands.extend(self.register.get_commands("wrregister", name = ['Conf_AddrEnable']))
        chip_sn_address = self.register.get_global_register_attributes("addresses", name="Chip_SN")
        #print chip_sn_address
        commands.extend(self.register.get_commands("rdregister", addresses = chip_sn_address))
        self.send_commands(commands)
    
        retfifo = self.device.ReadExternal(address = 0x8100, size = 8)
        size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
        #print 'SRAM FIFO SIZE: ' + str(size)
        
        fifo_data = self.device.FastBlockRead(4*size/2)
        #print 'fifo raw data:', fifo_data
        data = struct.unpack('>'+size/2*'I', fifo_data)
        #print 'raw data words:', data
        
        read_values = []
        for index, word in enumerate(data):
            fei4_data = FEI4Record(word, self.register.chip_flavor)
            if fei4_data == 'AR':
                read_value = FEI4Record(data[index+1], self.register.chip_flavor)['value']
                #print read_value
                read_values.append(read_value)
        
        #print read_values
        #sn_struct = struct.pack(len(read_values)*'H', *read_values)
        
        if len(read_values) == 0:
            chip_sn = None
        else:
            chip_sn = read_values[0]
            
        commands = []
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        
        # Bits [MSB-LSB] | [15]       | [14-6]       | [5-0]
        # Content        | reserved   | wafer number | chip number
    
        return chip_sn
    
    def test_global_register(self):
        self.configure_global()
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.send_commands(commands)
        self.readout_utils.reset_sram_fifo()
        commands = []
        self.register.set_global_register_value('Conf_AddrEnable', 1)
        commands.extend(self.register.get_commands("wrregister", name = 'Conf_AddrEnable'))
        read_from_address = range(1,64)
        checked_address = []
        commands.extend(self.register.get_commands("rdregister", addresses = read_from_address))
        self.send_commands(commands)
        
        retfifo = self.device.ReadExternal(address = 0x8100, size = 8)
        size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
        #print 'SRAM FIFO SIZE: ' + str(size)
        
        fifo_data = self.device.FastBlockRead(4*size/2)
        #print 'fifo raw data:', fifo_data
        data = struct.unpack('>'+size/2*'I', fifo_data)
        #print 'raw data words:', data
    
        number_of_errors = 0
        for index, word in enumerate(data):
            fei4_data = FEI4Record(word, self.register.chip_flavor)
            #print fei4_data
            if fei4_data == 'AR':
                read_value = FEI4Record(data[index+1], self.register.chip_flavor)['value']
                set_value = int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                checked_address.append(fei4_data['address'])
                #print int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                if read_value == set_value:
                    #print 'Register Test:', 'Address', fei4_data['address'], 'PASSED'
                    pass
                else:
                    number_of_errors += 1
                    print 'Register Test:', 'Address', fei4_data['address'], 'WRONG VALUE'
                    print 'Read:', read_value, 'Expected:', set_value
                    #raise Exception()
    
        commands = []
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        not_read_registers = set.difference(set(read_from_address), checked_address)
        not_read_registers = list(not_read_registers)
        not_read_registers.sort()
        for address in not_read_registers:
            print 'Register Test:', 'Address', address, 'ADDRESS NEVER OCCURRED'
            number_of_errors += 1
        return number_of_errors
        
    def test_pixel_register(self):
        self.configure_pixel()
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.send_commands(commands)
        self.readout_utils.reset_sram_fifo()
        
        commands = []
        self.register.set_global_register_value('Conf_AddrEnable', 1)
        self.register.set_global_register_value("S0", 0)
        self.register.set_global_register_value("S1", 0)
        self.register.set_global_register_value("SR_Clr", 0)
        self.register.set_global_register_value("CalEn", 0)
        self.register.set_global_register_value("DIGHITIN_SEL", 0)
        self.register.set_global_register_value("GateHitOr", 0)
        if self.register.is_chip_flavor('fei4a'):
            self.register.set_global_register_value("ReadSkipped", 0)
        self.register.set_global_register_value("ReadErrorReq", 0)
        self.register.set_global_register_value("StopClkPulse", 0)
        self.register.set_global_register_value("SR_Clock", 0)
        self.register.set_global_register_value("Efuse_Sense", 0)
        
        self.register.set_global_register_value("HITLD_IN", 0)
        self.register.set_global_register_value("Colpr_Mode", 0) # write only the addressed double-column
        self.register.set_global_register_value("Colpr_Addr", 0)
        
        self.register.set_global_register_value("Latch_En", 0)
        self.register.set_global_register_value("Pixel_Strobes", 0)
        
        commands.extend(self.register.get_commands("wrregister", name = ["Conf_AddrEnable", "S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadSkipped", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr", "Pixel_Strobes", "Latch_En"]))
        self.send_commands(commands)
        
        register_objects = self.register.get_pixel_register_objects(True, name = ["EnableDigInj"]) # check EnableDigInj first, because it is not latched
        register_objects.extend(self.register.get_pixel_register_objects(True, name = ["Imon", "Enable", "c_high", "c_low", "TDAC", "FDAC"]))
        #pprint.pprint(register_objects)
        #print "register_objects", register_objects
        number_of_errors = 0
        for register_object in register_objects:
            #pprint.pprint(register_object)
            pxstrobe = register_object.pxstrobe
            bitlength = register_object.bitlength
            for pxstrobe_bit_no in range(bitlength) if (register_object.littleendian == False) else reversed(range(bitlength)):
                do_latch = True
                commands = []
                try:
                    self.register.set_global_register_value("Pixel_Strobes", 2**(pxstrobe+pxstrobe_bit_no))
                    #print register_object.name
                    #print "bit_no", bit_no
                    #print "pxstrobes", 2**(pxstrobe+pxstrobe_bit_no)
                    
                except TypeError:
                    self.register.set_global_register_value("Pixel_Strobes", 0) # do not latch
                    do_latch = False
                    #print register_object.name
                    #print "bit_no", bit_no
                    #print "pxstrobes", 0
                commands.extend(self.register.get_commands("wrregister", name = ["Pixel_Strobes"]))
                self.send_commands(commands)
                
                for dc_no in range(40):
                    commands = []
                    self.register.set_global_register_value("Colpr_Addr", dc_no)
                    commands.extend(self.register.get_commands("wrregister", name = ["Colpr_Addr"]))
                    self.send_commands(commands)
                    
                    if do_latch == True:
                        commands = []
                        self.register.set_global_register_value("S0", 1)
                        self.register.set_global_register_value("S1", 1)
                        self.register.set_global_register_value("SR_Clock", 1)
                        commands.extend(self.register.get_commands("wrregister", name = ["S0", "S1", "SR_Clock"]))
                        commands.extend(self.register.get_commands("globalpulse", width = 0))
                        self.send_commands(commands)
                    commands = []
                    self.register.set_global_register_value("S0", 0)
                    self.register.set_global_register_value("S1", 0)
                    self.register.set_global_register_value("SR_Clock", 0)
                    commands.extend(self.register.get_commands("wrregister", name = ["S0", "S1", "SR_Clock"]))
                    self.send_commands(commands)
                    
                    register_bitset = self.register.get_pixel_register_bitset(register_object, pxstrobe_bit_no, dc_no)

                    commands = []
                    if self.register.is_chip_flavor('fei4b'):
                        self.register.set_global_register_value("SR_Read", 1)
                        commands.extend(self.register.get_commands("wrregister", name = ["SR_Read"]))
                    commands.extend([self.register.build_command("wrfrontend", pixeldata = register_bitset, chipid = self.register.chip_id)])
                    if self.register.is_chip_flavor('fei4b'):
                        self.register.set_global_register_value("SR_Read", 0)
                        commands.extend(self.register.get_commands("wrregister", name = ["SR_Read"]))
                    #print commands[0]
                    self.send_commands(commands)
                    #time.sleep( 0.2 )
    
                    retfifo = self.device.ReadExternal(address = 0x8100, size = 8)
                    size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
                    #print 'SRAM FIFO SIZE: ' + str(size)
                    
                    fifo_data = self.device.FastBlockRead(4*size/2)
                    #print 'fifo raw data:', fifo_data
                    data = struct.unpack('>'+size/2*'I', fifo_data)
                    #print 'raw data words:', data
                    
                    if len(data) == 0:
                        if do_latch:
                            print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'MISSING DATA'
                        else:
                            print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'MISSING DATA'
                        number_of_errors += 1
                    else:
                        expected_addresses = range(15, 672, 16)
                        seen_addresses = {}
                        for index, word in enumerate(data):
                            fei4_data = FEI4Record(word, self.register.chip_flavor)
                            #print fei4_data
                            if fei4_data == 'AR':
                                #print int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                                read_value = BitArray(uint=FEI4Record(data[index+1], self.register.chip_flavor)['value'], length = 16)
                                if do_latch == True:
                                    read_value.invert()
                                read_value = read_value.uint
                                read_address = fei4_data['address']
                                if read_address not in expected_addresses:
                                    if do_latch:
                                        print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'WRONG ADDRESS'
                                    else:
                                        print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'WRONG ADDRESS'
                                    number_of_errors += 1
                                else:
                                    if read_address not in seen_addresses:
                                        seen_addresses[read_address] = 1
                                        set_value = int(register_bitset[read_address-15:read_address+1])
                                        if read_value == set_value:
    #                                        if do_latch:
    #                                            print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'PASSED'
    #                                        else:
    #                                            print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'PASSED'
                                            pass
                                        else:
                                            number_of_errors += 1
                                            if do_latch:
                                                print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'WRONG VALUE'
                                            else:
                                                print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'WRONG VALUE'
                                            print 'Read:', read_value, 'Expected:', set_value
                                    else:
                                        seen_addresses[read_address] = seen_addresses[read_address]+1
                                        number_of_errors += 1
                                        if do_latch:
                                            print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'ADDRESS APPEARED MORE THAN ONCE'
                                        else:
                                            print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'ADDRESS APPEARED MORE THAN ONCE'

                        not_read_addresses = set.difference(set(expected_addresses), seen_addresses.iterkeys())
                        not_read_addresses = list(not_read_addresses)
                        not_read_addresses.sort()
                        for address in not_read_addresses:
                            number_of_errors += 1
                            if do_latch:
                                print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', address, 'ADDRESS NEVER OCCURRED'
                            else:
                                print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', address, 'ADDRESS NEVER OCCURRED'
    
    #                        for word in data:
    #                            print FEI4Record(word, self.register.chip_flavor)
        commands = []
        self.register.set_global_register_value("Pixel_Strobes", 0)
        self.register.set_global_register_value("Colpr_Addr", 0)
        self.register.set_global_register_value("S0", 0)
        self.register.set_global_register_value("S1", 0)
        self.register.set_global_register_value("SR_Clock", 0)
        if self.register.is_chip_flavor('fei4b'):
            self.register.set_global_register_value("SR_Read", 0)
            commands.extend(self.register.get_commands("wrregister", name = ["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock", "SR_Read"]))
        else:
            commands.extend(self.register.get_commands("wrregister", name = ["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock"]))
        # fixes bug in FEI4 (B only?): reading GR doesn't work after latching pixel register
        commands.extend(self.register.get_commands("wrfrontend", name = ["EnableDigInj"]))
        commands.extend(self.register.get_commands("runmode"))
        self.send_commands(commands)
        
        return number_of_errors
    
    def make_pixel_mask(self, default = 0, value = 1, mask = 6, column_offset = 0, row_offset = 0):
        dimension = (80,336)
        #value = np.zeros(dimension, dtype = np.uint8)
        mask_array = np.empty(dimension, dtype = np.uint8)
        mask_array.fill(default)
        # FE columns and rows start from 1
        odd_columns = range((0+column_offset)%2, 80, 2)
        even_columns = range((1+column_offset)%2, 80, 2)
        odd_rows = range((0+row_offset)%mask, 336, mask)
        even_row_offset = (int(math.floor(mask/2)+row_offset))%mask
        even_rows = range(0+even_row_offset, 336, mask)
        mask_array[odd_columns, odd_rows] = value # advanced indexing
        mask_array[even_columns, even_rows] = value
        return mask_array
        
    def make_pixel_mask_from_col_row(self, column = [], row = [], default = 0, value = 1):
        # FE columns and rows start from 1
        col_array = np.array(column)-1
        row_array = np.array(row)-1
        if np.any(col_array>=80) or np.any(col_array<0) or np.any(row_array>=336) or np.any(col_array<0):
            raise ValueError('Column and/or row out of range')
        dimension = (80,336)
        #value = np.zeros(dimension, dtype = np.uint8)
        mask = np.empty(dimension, dtype = np.uint8)
        mask.fill(default)
        mask[col_array, row_array] = value # advanced indexing
        return mask
    
def parse_key_value(filename, key, deletechars = ''):
    with open(filename, 'r') as f:
        return parse_key_value_from_file(f, key, deletechars)
            
def parse_key_value_from_file(f, key, deletechars = ''):
    for line in f.readlines():
        key_value = re.split("\s+|[\s]*=[\s]*", line)
        if (key_value[0].translate(None, deletechars).lower() == key.translate(None, deletechars).lower()):
            if len(key_value) > 1:
                print key_value
                print len(key_value)
                return key_value[0].translate(None, deletechars).lower(), key_value[1].translate(None, deletechars).lower()
            else:
                raise ValueError('Value not found')
        else:
            return None