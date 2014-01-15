from scan.scan import ScanBase

import time
from datetime import datetime

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

# scan configuration dictionary to set up scan parameters
scan_configuration = {
    "some_keyword_parameter": "parameter was set",
    "some_other_keyword_parameter": "parameter was set"
}


# inherit from ScanBase class
class ExampleScan(ScanBase):
    # a class variable
    some_class_varible = None

    # initializing the newly-created class instance
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        # accessing inherited methods that have been overridden in a class
        super(ExampleScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="example_scan")

        # a public instance variable
        self.some_public_variable = 123

        # a "private" instance variable (They don't exist in Python. However, there is a convention that is followed by most Python code: a name prefixed with an underscore should be treated as a non-public part of the API)
        self._some_private_variable = 123

        # a name mangled instance variable (Any identifier of the form __spam (at least two leading underscores, at most one trailing underscore) is textually replaced with _classname__spam, where classname is the current class name with leading underscore(s) stripped)
        self.__some_name_mangling_variable = 123

    # example code: how to define a function/method object
    def some_function(self, text):
        print text

    def scan(self, some_keyword_parameter="parameter was not set", **kwargs):

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
            print(datetime.now() - start_time)
            time.sleep(1)

            # example code: defining some abort condition
            if datetime.now() - start_time > 600:  # abort after 10min runtime
                break


        # example code: how to start readout
        self.readout.stop()

        # example code: how to use logger
        logging.info('thread ends after %.1f seconds' % (datetime.now() - start_time).total_seconds())
        logging.warning('last message from thread')

if __name__ == "__main__":
    import configuration
    # dereference device_configuration dictionary and use it for setting the parameters
    # open configuration.py to change device parameters
    scan = ExampleScan(**configuration.device_configuration)
    # when use_thread is true (scan() runs in a thread), start() is non-blocking, otherwise blocking
    scan.start(use_thread=True, configure=True, **scan_configuration)
    # when use_thread is true (scan() runs in a thread), stop() is blocking until timeout is reached (if timeout is None, wait for scan has completed), otherwise non-blocking
    scan.stop(timeout=5)
