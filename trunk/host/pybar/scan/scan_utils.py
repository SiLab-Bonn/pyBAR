import ast
from bitarray import bitarray
from fei4.register_utils import make_pixel_mask
import logging


def scan_loop(self, command, repeat_command=100, use_delay=True, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], disable_shift_masks=[], restore_shift_masks=True, mask=None, double_column_correction=False):
    '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).

    Parameters
    ----------
    command : BitVector
        (FEI4) command that will be sent out serially.
    repeat_command : int
        The number of repetitions command will be sent out each mask step.
    use_delay : bool
        Add additional delay to the command (append zeros). This helps to avoid FE data errors because of sending to many commands to the FE chip.
    mask_steps : int
        Number of mask steps.
    enable_mask_steps : list, tuple
        List of mask steps which will be applied. Default is all mask steps. From 0 to (mask-1). A value equal None or empty list will select all mask steps.
    enable_double_columns : list, tuple
        List of double columns which will be enabled during scan. Default is all double columns. From 0 to 39 (double columns counted from zero). A value equal None or empty list will select all double columns.
    same_mask_for_all_dc : bool
        Use same mask for all double columns. This will only affect all shift masks (see enable_shift_masks). Enabling this is in general a good idea since all double columns will have the same configuration and the scan speed can increased by an order of magnitude.
    bol_function : function
        Begin of loop function that will be called each time before sending command. Argument is a function pointer (without braces) or functor.
    eol_function : function
        End of loop function that will be called each time after sending command. Argument is a function pointer (without braces) or functor.
    digital_injection : bool
        Enables digital injection. C_High and C_Low will be disabled.
    enable_shift_masks : list, tuple
        List of enable pixel masks which will be shifted during scan. Mask set to 1 for selected pixels else 0.
    disable_shift_masks : list, tuple
        List of disable pixel masks which will be shifted during scan. Mask set to 0 for selected pixels else 1.
    restore_shift_masks : bool
        Writing the initial (restored) FE pixel configuration into FE after finishing the scan loop.
    mask : array-like
        Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked pixel. Masked pixels will be disabled during shifting of the enable shift masks, and enabled during shifting disable shift mask.
    double_column_correction : str, bool, list, tuple
        Enables double column PlsrDAC correction. If value is a filename (string) or list/tuple, the default PlsrDAC correction will be overwritten. First line of the file must be a Python list ([0, 0, ...])
    '''
    if not isinstance(command, bitarray):
        raise TypeError

    # get PlsrDAC correction
    if isinstance(double_column_correction, basestring):  # from file
        with open(double_column_correction) as fp:
            plsr_dac_correction = list(ast.literal_eval(fp.readline().strip()))
    elif isinstance(double_column_correction, (list, tuple)):  # from list/tuple
        plsr_dac_correction = list(double_column_correction)
    else:  # default
        if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) and "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_High']
        elif "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_Med']
        elif "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_Low']
    # initial PlsrDAC value for PlsrDAC correction
    initial_plsr_dac = self.register.get_global_register_value("PlsrDAC")
    # create restore point
    restore_point_name = self.scan_id + '_scan_loop'
    self.register.create_restore_point(name=restore_point_name)

    # pre-calculate often used commands
    conf_mode_command = self.register.get_commands("confmode")[0]
    run_mode_command = self.register.get_commands("runmode")[0]
    delay = self.register.get_commands("zeros", mask_steps=mask_steps)[0]
    if use_delay:
        scan_loop_command = command + delay
    else:
        scan_loop_command = command

    def enable_columns(dc):
        if digital_injection:
            return [dc * 2 + 1, dc * 2 + 2]
        else:  # analog injection
            if dc == 0:
                return [1]
            elif dc == 39:
                return [78, 79, 80]
            else:
                return [dc * 2, dc * 2 + 1]

    def write_double_columns(dc):
        if digital_injection:
            return dc
        else:  # analog injection
            if dc == 0:
                return [0]
            elif dc == 39:
                return [38, 39]
            else:
                return [dc - 1, dc]

    def get_dc_address_command(dc):
        commands = []
        commands.append(conf_mode_command)
        self.register.set_global_register_value("Colpr_Addr", dc)
        commands.append(self.register.get_commands("wrregister", name=["Colpr_Addr"])[0])
        if double_column_correction:
            self.register.set_global_register_value("PlsrDAC", initial_plsr_dac + plsr_dac_correction[dc])
            commands.append(self.register.get_commands("wrregister", name=["PlsrDAC"])[0])
        commands.append(run_mode_command)
        return self.register_utils.concatenate_commands(commands, byte_padding=True)

    if enable_mask_steps is None or not enable_mask_steps:
        enable_mask_steps = range(mask_steps)

    if enable_double_columns is None or not enable_double_columns:
        enable_double_columns = range(40)

    # preparing for scan
    commands = []
    commands.append(conf_mode_command)
    if digital_injection is True:
        # check if C_High and/or C_Low is in enable_shift_mask and/or disable_shift_mask
        if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_High".lower() in map(lambda x: x.lower(), disable_shift_masks):
            raise ValueError('C_High must not be shift mask when using digital injection')
        if "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_Low".lower() in map(lambda x: x.lower(), disable_shift_masks):
            raise ValueError('C_Low must not be shift mask when using digital injection')
        # turn off all injection capacitors by default
        self.register.set_pixel_register_value("C_High", 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_High"]))
        self.register.set_pixel_register_value("C_Low", 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_Low"]))
        self.register.set_global_register_value("DIGHITIN_SEL", 1)
#             self.register.set_global_register_value("CalEn", 1)  # for GlobalPulse instead Cal-Command
    else:
        self.register.set_global_register_value("DIGHITIN_SEL", 0)
        # setting EnableDigInj to 0 not necessary since DIGHITIN_SEL is turned off
#             self.register.set_pixel_register_value("EnableDigInj", 0)

    commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
    self.register_utils.send_commands(commands, concatenate=True)

    for mask_step in enable_mask_steps:
        if self.stop_run.is_set():
            break
        commands = []
        commands.append(conf_mode_command)
        if same_mask_for_all_dc:  # generate and write first mask step
            if disable_shift_masks:
                curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask is not None else True, name=disable_shift_masks))
            if enable_shift_masks:
                curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask is not None else True, name=enable_shift_masks))
#                 plt.clf()
#                 plt.imshow(curr_en_mask.T, interpolation='nearest', aspect="auto")
#                 plt.pcolor(curr_en_mask.T)
#                 plt.colorbar()
#                 plt.savefig('mask_step' + str(mask_step) + '.pdf')
            if digital_injection is True:  # write EnableDigInj last
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask is not None else True, name=['EnableDigInj']))
                # write DIGHITIN_SEL since after mask writing it is disabled
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
        else:  # set masks to default values
            if disable_shift_masks:
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 1), disable_shift_masks)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=disable_shift_masks))
            if enable_shift_masks:
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 0), [shift_mask_name for shift_mask_name in enable_shift_masks])
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=enable_shift_masks))
            if digital_injection is True:  # write EnableDigInj last
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=['EnableDigInj']))
                # write DIGHITIN_SEL since after mask writing it is disabled
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
        self.register_utils.send_commands(commands, concatenate=True)
        logging.info('%d injection(s): mask step %d %s' % (repeat_command, mask_step, ('[%d - %d]' % (enable_mask_steps[0], enable_mask_steps[-1])) if len(enable_mask_steps) > 1 else ('[%d]' % enable_mask_steps[0])))

        if same_mask_for_all_dc:  # fast loop
            # set repeat, should be 1 by default when arriving here
            self.dut['cmd']['CMD_REPEAT'] = repeat_command

            # get DC command for the first DC in the list, DC command is byte padded
            # fill CMD memory with DC command and scan loop command, inside the loop only overwrite DC command
            dc_address_command = get_dc_address_command(enable_double_columns[0])
            self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
            self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

            for dc in enable_double_columns:
                if self.stop_run.is_set():
                    break
                if dc != 0:  # full command is already set before loop
                    # get DC command before wait to save some time
                    dc_address_command = get_dc_address_command(dc)
                    self.register_utils.wait_for_command()
                    if eol_function:
                        eol_function()  # do this after command has finished
                    # only set command after FPGA is ready
                    # overwrite only the DC command in CMD memory
                    self.register_utils.set_command(dc_address_command, set_length=False)  # do not set length here, because it was already set up before the loop

                if bol_function:
                    bol_function()

                self.dut['cmd']['START']

            # wait here before we go on because we just jumped out of the loop
            self.register_utils.wait_for_command()
            if eol_function:
                eol_function()
            self.dut['cmd']['START_SEQUENCE_LENGTH'] = 0
        else:  # slow loop
            dc = enable_double_columns[0]
            ec = enable_columns(dc)
            dcs = write_double_columns(dc)
            commands = []
            commands.append(conf_mode_command)
            if disable_shift_masks:
                curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks))
            if enable_shift_masks:
                curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks))
            if digital_injection is True:
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=['EnableDigInj']))
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
            self.register_utils.send_commands(commands, concatenate=True)

            dc_address_command = get_dc_address_command(dc)
            self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
            self.dut['cmd']['CMD_REPEAT'] = repeat_command
            self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

            for dc in enable_double_columns:
                if self.stop_run.is_set():
                    break
                if dc != 0:  # full command is already set before loop
                    ec = enable_columns(dc)
                    dcs = write_double_columns(dc)
                    dcs.extend(write_double_columns(enable_double_columns[dc - 1]))
                    commands = []
                    commands.append(conf_mode_command)
                    if disable_shift_masks:
                        curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                        map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks))
                    if enable_shift_masks:
                        curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                        map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks))
                    if digital_injection is True:
                        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=['EnableDigInj']))
                        self.register.set_global_register_value("DIGHITIN_SEL", 1)
                        commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
                    dc_address_command = get_dc_address_command(dc)

                    self.register_utils.wait_for_command()
                    if eol_function:
                        eol_function()  # do this after command has finished
                    self.register_utils.send_commands(commands, concatenate=True)

                    self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                    self.dut['cmd']['CMD_REPEAT'] = repeat_command
                    self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                if bol_function:
                    bol_function()

                self.dut['cmd']['START']

            self.register_utils.wait_for_command()
            if eol_function:
                eol_function()
            self.dut['cmd']['START_SEQUENCE_LENGTH'] = 0

    # restoring default values
    self.register.restore(name=restore_point_name)
    self.register_utils.configure_global()  # always restore global configuration
    if restore_shift_masks:
        commands = []
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=disable_shift_masks))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=enable_shift_masks))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name="EnableDigInj"))
        self.register_utils.send_commands(commands)
