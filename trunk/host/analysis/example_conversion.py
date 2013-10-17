"""This is an example module how to use the raw data analyzer. It takes a table with FE-I4 raw data and interprets, histograms and plots it."""
chip_flavor = 'fei4a'
input_file = "K:\\test_in.h5"
output_file = "K:\\test_out.h5"
scan_data_filename = "K:\\test_out" 

from analyze_raw_data import AnalyzeRawData

with AnalyzeRawData(input_file = input_file, output_file = output_file) as analyze_raw_data:
    analyze_raw_data.create_hit_table = True # can be set to false to omit hit creation, can save some time, std. setting is false
    analyze_raw_data.create_threshold_hists = False # makes only sense if threshold scan data is analyzed, std. setting is false
    analyze_raw_data.interpreter.set_warning_output(True) # std. setting is True
    analyze_raw_data.interpreter.debug_events(0,0,True) # events to be printed onto the console for debugging, usually deactivated
    analyze_raw_data.interpret_word_table(FEI4B = True if(chip_flavor == 'fei4b') else False) # the actual start conversion command
    analyze_raw_data.interpreter.print_summary() # prints the interpreter summary
    analyze_raw_data.plotHistograms(scan_data_filename = scan_data_filename) # plots all activated histograms