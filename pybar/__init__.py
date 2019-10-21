from pkg_resources import get_distribution, DistributionNotFound


__version__ = None  # required for initial installation

try:
    __version__ = get_distribution("pyBAR").version
except DistributionNotFound:
    __version__ = "(local)"


from pybar.run_manager import RunManager, run_status
from pybar.scans import *


__all__ = ["__version__", "RunManager", "run_status", "HitOrCalibration", "create_hitor_calibration", "PlsrDacTransientCalibration", "PlsrDacCalibration", "plot_pulser_dac", "PulserDacCorrectionCalibration", "ThresholdCalibration", "create_threshold_calibration", "TotCalibration", "AnalogScan", "CrosstalkScan", "DigitalScan", "ExtTriggerGdacScan", "StopModeExtTriggerScan", "ExtTriggerScan", "Fei4SelfTriggerScan", "HitDelayScan", "IleakScan", "InitScan", "IVScan", "FastThresholdScan", "ThresholdScan", "RegisterTest", "TdcTest", "FdacTuning", "FeedbackTuning", "Fei4Tuning", "GdacTuning", "GdacTuningStandard", "HotPixelTuning", "MergedPixelsTuning", "NoiseOccupancyTuning", "StuckPixelTuning", "TdacTuning", "ThresholdBaselineTuning", "TluTuning"]
