from scan.scan import ScanBase

import time
from datetime import datetime

import logging
logging.basicConfig(level=logging.INFO, format = "%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

# inherit from ScanBase class
class ExampleScan(ScanBase):
    def __init__(self, configuration_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_example", scan_data_path = None):
        # accessing inherited methods that have been overridden in a class
        super(ExampleScan, self).__init__(configuration_file = configuration_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
        # a public instance variable
        self.some_public_variable = 123
        
        # a "private" instance variable (They don't exist in Python. However, there is a convention that is followed by most Python code: a name prefixed with an underscore should be treated as a non-public part of the API)
        self._some_private_variable = 123
        
        # a name mangled instance variable (Any identifier of the form __spam (at least two leading underscores, at most one trailing underscore) is textually replaced with _classname__spam, where classname is the current class name with leading underscore(s) stripped)
        self.__some_name_mangling_variable = 123
        
# example code: how to define a function/method object
    def some_function(self, text):
        print text
        
    def scan(self, some_keyword_parameter = "parameter was not set", **kwargs):
        
        ######################################################################################
        #                                                                                    #
        #                                 Put your code here!                                #
        #                                                                                    #
        ######################################################################################
        
        # example code: how to start readout
        self.readout.start()
        
        # example code: how to profile your code
        import cProfile
        pr = cProfile.Profile()
        pr.enable()
        # ***put your code to profile here***
        pr.disable()
        pr.print_stats('cumulative')

        # example code: how to set function arguments
        print some_keyword_parameter
        
        # example code: how to set function keyword arguments
        print kwargs["some_other_keyword_parameter"]
        
        # example code: how to call function abject from a thread
        self.some_function("this is some text")

        # example code: setting up some variables
        start_time = datetime.now()
        some_parameter = True
        # example code: main scan loop with scan parameter (some_parameter) and abort condition (self.stop_thread_event)
        # note: to use Ctrl-C to abort scan loop set parameter use_thread to True: scan.start(use_thread=True)
        while some_parameter and not self.stop_thread_event.is_set():
            print(datetime.now()-start_time)
            time.sleep(1)
            
            # example code: defining some abort condition
            if datetime.now()-start_time > 600: # abort after 10min runtime
                break
            

        # example code: how to start readout
        self.readout.stop()
        
        # example code: how to use logger
        logging.info('thread ends after %.1f seconds' % (datetime.now()-start_time).total_seconds())
        logging.warning('last message from thread')

if __name__ == "__main__":
    import configuration
    scan = ExampleScan(configuration_file = configuration.configuration_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    # when use_thread is true (scan() runs in a thread), start() is non-blocking, otherwise blocking
    scan.start(use_thread=True, configure=True, some_keyword_parameter = "parameter was set", some_other_keyword_parameter = "parameter was set")
    # when use_thread is true (scan() runs in a thread), stop() is blocking until timeout is reached (if timeout is None, wait for scan has completed), otherwise non-blocking
    scan.stop(timeout=5)
