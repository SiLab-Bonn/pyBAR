import BitVector

import logging
logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class FEI4ScanUtils(object):
    def __init__(self, register, register_utils):
        self.register = register
        self.register_utils = register_utils
    
    def base_scan(self, command, repeat = 100, hardware_repeat = True, mask = 3, mask_steps = None, double_columns = None, same_mask_for_all_dc = False, eol_function = None, digital_injection = False, enable_c_high = None, enable_c_low = None, shift_masks = ["Enable", "C_High", "C_Low"]):
        '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).
        
        Parameters
        ----------
        command : BitVector
            (FEI4) command that will be sent out serially.
        repeat : int
            Number of injections.
        hardware_repeat : bool
            If true, use FPGA to repeat commands. In general this is much faster than doing this in software.
        mask : int
            Number of mask steps.
        mask_steps : list, tuple
            List of mask steps which will be applied. Default is all mask steps. From 0 to (mask-1).
        double_columns : list, tuple
            List of double columns which will be enabled during scan. Default is all double columns. From 0 to 39 (double columns counted from zero).
        same_mask_for_all_dc : bool
            Use same mask for all double columns. Enabling this is in general not a good idea since all double columns will have the same configuration but the scan speed can increased by an order of magnitude.  
        eol_function : function
            End of loop function that will be called each time the innermost loop ends.  
        digital_injection : bool
            Enables digital injection.
        enable_c_high : bool
            Enables C_High pixel mask. Will be overwritten by shift_mask.
        enable_c_low : bool
            Enables C_Low pixel mask. Will be overwritten by shift_mask.
        shift_masks : list, tuple
            List of pixel masks that will be shifted. 
        '''
        if not isinstance(command, BitVector.BitVector):
            raise TypeError
        
        # pre-calculate often used commands
        conf_mode_command = self.register.get_commands("confmode")
        run_mode_command = self.register.get_commands("runmode")
        
        if mask_steps == None or mask_steps == []:
            mask_steps = range(mask)
            
        if double_columns == None or double_columns == []:
            double_columns = range(40)
        
        # preparing for scan
        commands = []
        commands.extend(conf_mode_command)
        if digital_injection == True:
            #self.register.set_global_register_value("CalEn", 1) # for GlobalPulse instead Cal-Command
            self.register.set_global_register_value("DIGHITIN_SEL", 1)
        else:
            self.register.set_global_register_value("DIGHITIN_SEL", 0)
            self.register.set_pixel_register_value("EnableDigInj", 0)
        commands.extend(self.register.get_commands("wrregister", name = ["DIGHITIN_SEL"]))
        if(enable_c_high != None):
            self.register.set_pixel_register_value("C_High", 1 if enable_c_high else 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = True, name = ["C_High"]))
        if(enable_c_low != None):
            self.register.set_pixel_register_value("C_Low", 1 if enable_c_low else 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = True, name = ["C_Low"]))
        self.register_utils.send_commands(commands)
            
        for mask_step in mask_steps:# range(mask_steps):
            commands = []
            commands.extend(conf_mode_command)
            mask_array = self.register_utils.make_pixel_mask(mask = mask, row_offset = mask_step)
            #plt.imshow(np.transpose(mask_array), interpolation='nearest', aspect="auto")
            #plt.pcolor(np.transpose(mask_array))
            #plt.colorbar()
            #plt.savefig('mask_step'+str(mask_step)+'.eps')
            map(lambda mask: self.register.set_pixel_register_value(mask, mask_array), [shift_mask for shift_mask in shift_masks if (shift_mask.lower() != "EnableDigInj".lower())])
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = same_mask_for_all_dc, name = shift_masks))
            if digital_injection == True: # TODO: write EnableDigInj to FE or do it manually?
                self.register.set_pixel_register_value("EnableDigInj", mask_array)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = same_mask_for_all_dc, name = ["EnableDigInj"]))
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("wrregister", name = ["DIGHITIN_SEL"])) # write DIGHITIN_SEL mask last
#             else:
#                 commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = True, name = ["EnableDigInj"]))
            self.register_utils.send_commands(commands)
            logging.info('%d injection(s): mask step %d' % (repeat, mask_step))
            
            for dc in double_columns:
                commands = []
                #commands.extend(conf_mode_command)
                self.register.set_global_register_value("Colpr_Addr", dc)
                # pack all commands into one bit vector, speeding up of inner loop
                #commands.append(conf_mode_command[0]+BitVector.BitVector(size = 10)+self.register.get_commands("wrregister", name = ["Colpr_Addr"])[0]+BitVector.BitVector(size = 10)+run_mode_command[0])
                commands.append(conf_mode_command[0]+self.register.get_commands("wrregister", name = ["Colpr_Addr"])[0]+run_mode_command[0])
                #commands.extend(self.register.get_commands("wrregister", name = ["Colpr_Addr"]))
                #commands.extend(run_mode_command)
                self.register_utils.send_commands(commands)
                
                #print repeat, 'injections:', 'mask step', mask_step, 'dc', dc
                bit_length = self.register_utils.set_command(command)
                if hardware_repeat == True:
                    self.register_utils.send_command(repeat = repeat, wait_for_cmd = True, command_bit_length = bit_length)
                else:
                    for _ in range(repeat):
                        self.register_utils.send_command()
                try:
                    eol_function()
                except TypeError:
                    pass

        # setting back to default values
        commands = []
        if digital_injection == True:
            #self.register.set_global_register_value("CalEn", 0) # for GlobalPulse instead Cal-Command
            self.register.set_global_register_value("DIGHITIN_SEL", 0)
            commands.extend(self.register.get_commands("wrregister", name = ["DIGHITIN_SEL"]))
        self.register.set_global_register_value("Colpr_Addr", 0)
        self.register.set_global_register_value("Colpr_Mode", 0)
        commands.extend(self.register.get_commands("wrregister", name = ["Colpr_Addr", "Colpr_Mode"]))
        self.register_utils.send_commands(commands)
