""" Scan to inject charge with an external pulser. A trigger signal (3.3V logic level, TX1 at MultiIO board)
    is generated when the CAL command is issued. This trigger can be used to trigger the external pulser.
"""
import logging

from daq.readout import save_raw_data_from_data_dict_iterable

from scan.scan import ScanBase


local_configuration = {
    "mask_steps": 6,
    "repeat_command": 1000,
    "enable_double_columns": None
}


class ExtInjScan(ScanBase):
    scan_id = "ext_injection_scan"

    def scan(self):
        self.readout.start()

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", mask_steps=self.mask_steps)[0]
        self.scan_loop(cal_lvl1_command, repeat_command=self.repeat_command, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=self.enable_double_columns, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

        self.readout.stop()

        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_id)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(pdf_filename=self.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = ExtInjScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=False, **local_configuration)
    scan.stop()

#
# # Chip Parameters
# Flavor FEI4B
# Chip_ID 8 Broadcast = 8
#
# # Global Registers
# Amp2Vbn 79
# Amp2Vbp 85
# Amp2Vbpff 50 Fixes noise on power supply and dead pixels when irradiated
# Amp2VbpFol 26
# CalEn 0
# Chip_SN 0
# CLK0_S0 0
# CLK0_S1 0
# CLK0_S2 1
# CLK1_S0 0
# CLK1_S1 0
# CLK1_S2 0
# Clk2OutCnfg 0
# CMDcnt 11
# Colpr_Addr 0
# Colpr_Mode 0
# Conf_AddrEnable 1
# DIGHITIN_SEL 0
# DINJ_OVERRIDE 0
# DisableColumnCnfg 0
# DisVbn 26
# Efuse_Sense 0
# EmptyRecordCnfg 0
# EN_160M 1
# EN_320M 0
# EN_40M 1
# EN_80M 0
# EN_PLL 1
# #ErrorMask 0
# ErrorMask 17920 disabled FiFo full (Error Code 9) and L1A counter (Error Code 14)
# EventLimit 0
# ExtAnaCalSW 1
# ExtDigCalSW 0
# FdacVbn 50
# GADCCompBias 100
# GADCSel 0
# GADCStart 0
# GADCVref 170
# GateHitOr 0
# HitDiscCnfg 0
# HITLD_IN 0
# Latch_En 0
# LvdsDrvEn 1
# LvdsDrvIref 171
# LvdsDrvSet06 1
# LvdsDrvSet12 1
# LvdsDrvSet30 1
# LvdsDrvVos 105
# MonleakRange 0
# No8b10b 0
# Pixel_Strobes 0
# PllIbias 88
# PllIcp 28
# PlsrDAC 0
# PlsrDacBias 96
# PlsrDelay 2
# PlsrIdacRamp 180
# PlsrPwr 0
# PlsrRiseUpTau 7
# PlsrVgOpAmp 255
# PrmpVbnFol 106
# PrmpVbnLcc 0
# PrmpVbp 43
# PrmpVbpMsbEn 0
# #PrmpVbpf 150
# PrmpVbpf 100
# PrmpVbp_L 43
# PrmpVbp_R 43
# ReadErrorReq 0
# S0 0
# S1 0
# SELB 0
# SmallHitErase 0
# SR_Clock 0
# SR_Clr 0
# SR_Read 0
# StopClkPulse 0
# StopModeCnfg 0
# TdacVbp 100 DAC changed from FEI4A to B
# TempSensDiodeBiasSel 0
# TempSensDisable 0
# TempSensIbias 0
# Trig_Count 0
# Trig_Lat 210
# VrefAnTune 0 max. analog voltage (approx. 1.45V)
# VrefDigTune 100 digital voltage (1.2V)
# Vthin_AltCoarse 3
# Vthin_AltFine 240
#
# # Pixel Registers
# C_High 1 C:\pyats\trunk\host\config\fei4default\masks\c_high.dat
# C_Low 1 C:\pyats\trunk\host\config\fei4default\masks\c_low.dat
# Enable 1 C:\pyats\trunk\host\config\fei4default\masks\enable.dat
# EnableDigInj 0 C:\pyats\trunk\host\config\fei4default\masks\enablediginj.dat
# FDAC 7 C:\pyats\trunk\host\config\fei4default\fdacs\fdac.dat
# Imon 0 C:\pyats\trunk\host\config\fei4default\masks\imon.dat
# TDAC 15 C:\pyats\trunk\host\config\fei4default\tdacs\tdac.dat
#
# # Calibration Parameters
# C_Inj_Low 0
# C_Inj_High 0
# Vcal_Coeff_0 0
# Vcal_Coeff_1 0

