from yaml import safe_load
import datetime
import os
import re
import collections
from threading import Lock
from multiprocessing import dummy as multiprocessing
import threading
import sys
import functools
import traceback
import signal
import abc
import logging

RunStatus = collections.namedtuple('RunStatus', ['running', 'finished', 'aborted', 'crashed'])


class RunAborted(Exception):
    pass


class RunBase():
    __metaclass__ = abc.ABCMeta

    _status = RunStatus(running='RUNNING', finished='FINISHED', aborted='ABORTED', crashed='CRASHED')

    def __init__(self, working_dir, **kwargs):
        """Initialize object."""
        self._working_dir = working_dir
        self._run_number = None
        self._run_status = None
        self.file_lock = Lock()

    def __call__(self):
        self.init()
        try:
            self.run()
        except RunAborted as e:
            self._run_status = self._status.aborted
            logging.warning('Aborting run %s: %s' % (self.run_number, e))
        except Exception as e:
            self._run_status = self._status.crashed
            logging.error('Exception during run %s: %s' % (self.run_number, traceback.format_exc()))
            with open(os.path.join(self.working_dir, "crash" + ".log"), 'a+') as f:
                f.write('-------------------- Run %i --------------------\n' % self.run_number)
                traceback.print_exc(file=f)
                f.write('\n')
        else:
            self._run_status = self._status.finished
        self.cleanup()
        return self.run_status

    @property
    def working_dir(self):
        return self._working_dir

    @property
    def run_number(self):
        return self._run_number

    @property
    def run_status(self):
        return self._run_status

    def init(self):
        """Initialization before a new run."""
        self._run_status = self._status.running
        self._write_run_number()
        logging.info('Starting run %d in %s' % (self.run_number, self.working_dir))

    @abc.abstractmethod
    def run(self):
        """The run."""
        pass

    def cleanup(self):
        """Cleanup after a new run."""
        self._write_run_status(self.run_status)
        if self.run_status == self._status.finished:
            log_status = logging.INFO
        elif self.run_status == self._status.aborted:
            log_status = logging.WARNING
        else:
            log_status = logging.ERROR
        logging.log(log_status, 'Stopped run %d in %s with status %s' % (self.run_number, self.working_dir, self.run_status))

    @abc.abstractmethod
    def abort(self, msg=None):
        """Aborting a run."""
        pass

    def _get_run_numbers(self, status=None):
        run_numbers = {}
        with self.file_lock:
            if not os.path.exists(self.working_dir):
                os.makedirs(self.working_dir)
            # In Python 2.x, open on all POSIX systems ultimately just depends on fopen.
            with open(os.path.join(self.working_dir, "run" + ".cfg"), 'r') as f:
                f.seek(0)
                for line in f.readlines():
                    try:
                        number_parts = re.findall('\d+\s+', line)
                        parts = re.split('\s+', line)
                        if status:
                            if parts[1] in status:
                                run_number = int(number_parts[0])
                            else:
                                continue
                        else:
                            run_number = int(number_parts[0])
                    except IndexError:
                        continue
                    if line[-1] != '\n':
                        line = line + '\n'
                    run_numbers[run_number] = line
        return run_numbers

    def _write_run_number(self):
        run_numbers = self._get_run_numbers()
        if not run_numbers:
            self._run_number = 0
        else:
            self._run_number = max(dict.iterkeys(run_numbers)) + 1
        run_numbers[self.run_number] = str(self.run_number) + ' ' + 'RUNNING' + ' ' + str(datetime.datetime.now()) + '\n'
        with self.file_lock:
            with open(os.path.join(self.working_dir, "run" + ".cfg"), "w") as f:
                for value in dict.itervalues(run_numbers):
                    f.write(value)

    def _write_run_status(self, status_msg):
        run_numbers = self._get_run_numbers()
        if not run_numbers:
            run_numbers[self.run_number] = str(self.run_number) + ' ' + status_msg + ' ' + str(datetime.datetime.now()) + '\n'
        else:
            parts = re.split('\s+', run_numbers[self.run_number])
            parts[1] = status_msg
            run_numbers[self.run_number] = ' '.join(parts[:-1]) + ' ' + str(datetime.datetime.now()) + '\n'
        with self.file_lock:
            with open(os.path.join(self.working_dir, "run" + ".cfg"), "w") as f:
                for value in dict.itervalues(run_numbers):
                    f.write(value)


def thunkify(thread_name):
    """Make a function immediately return a function of no args which, when called,
    waits for the result, which will start being processed in another thread.
    Taken from https://wiki.python.org/moin/PythonDecoratorLibrary.
    """

    def actual_decorator(f):
        @functools.wraps(f)
        def thunked(*args, **kwargs):
            result = [None]
            exc = [False, None]
#             wait_event = threading.Event()

            def worker_func():
                try:
                    func_result = f(*args, **kwargs)
                    result[0] = func_result
                except Exception as e:
                    exc[0] = True
                    exc[1] = sys.exc_info()
                    logging.error("RunThread has thrown an exception:\n%s" % (traceback.format_exc()))
#                 finally:
#                     wait_event.set()

            worker_thread = threading.Thread(target=worker_func, name=thread_name if thread_name else None)
            worker_thread.daemon = True

            def thunk():
                worker_thread.join()
#                 wait_event.wait()
                if exc[0]:
                    raise exc[1][0], exc[1][1], exc[1][2]
                return result[0]

            worker_thread.start()
#             threading.Thread(target=worker_func, name=thread_name if thread_name else None).start()
            return thunk
        return thunked
    return actual_decorator


class RunManager(object):
    def __init__(self, conf):
        '''Run Manager is taking care of initialization and execution of runs.

        Parameters
        ----------
        conf : str, dict, file
            Configuration for the run.
        '''
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True

            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)

        self.conf = self.open_conf(conf)

    @staticmethod
#     @thunkify('RunThread')
    def run_run(run, conf):
        '''Runs a run in another thread. Non-blocking.

        Parameters
        ----------
        run : class
            Run class.
        conf : str, dict, file
            Configuration for the run.

        Returns
        -------
        Function, which blocks when called, waits for the end of the run, and returns run status.
        '''
        conf = RunManager.open_conf(conf)
        run = run(**conf)

        @thunkify('RunThread')
        def run_run_in_thread():
            run()

        return run_run_in_thread()

    @staticmethod
    def open_conf(conf):
        if not conf:
            return None
        elif isinstance(conf, basestring):  # parse the first YAML document in a stream
            stream = open(conf)
            return safe_load(stream)
        elif isinstance(conf, file):  # parse the first YAML document in a stream
            return safe_load(conf)
        else:  # conf is already a dict
            return conf

    def start(self):
        '''Starting scan.

        Parameters
        ----------
        configure : bool
            If true, configure FE before starting scan.scan().
        restore_configuration : bool
            Restore FE configuration after finishing scan.scan().
        use_thread : bool
            If true, scan.scan() is running in a separate thread. Only then Ctrl-C can be used to interrupt scan loop.
        do_global_reset : bool
            Do a FE Global Reset before sending FE configuration.
        kwargs : any
            Any keyword argument passed to scan.start() will be forwarded to scan.scan(). Please note: scan.start() keyword arguments will merged with class keyword arguments
        '''
        pass
#         self.scan_is_running = True
#         self.scan_aborted = False
# 
#         self.use_thread = use_thread
#         if self.scan_thread is not None:
#             raise RuntimeError('Scan thread is already running')
# 
#         self.stop_thread_event.clear()
# 
#         logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan.scan_id, self.run_numbers, self.scan_data_output_path))
#         if use_thread:
#             self.scan_thread = Thread(target=self.scan.scan, name='%s with ID %d' % (self.scan.scan_id, self.run_numbers), kwargs=None)  # kwargs=self._scan_configuration)
#             self.scan_thread.daemon = True  # Abruptly close thread when closing main thread. Resources may not be released properly.
#             self.scan_thread.start()
#             logging.info('Press Ctrl-C to stop scan loop')
#             signal.signal(signal.SIGINT, self._signal_handler)
#         else:
#             self.scan.scan()  # **self._scan_configuration)

    def stop(self):
        '''Stopping scan. Cleaning up of variables and joining thread (if existing).

        '''
        pass
#         if (self.scan_thread is not None) ^ self.use_thread:
#             if self.scan_thread is None:
#                 pass
# #                 logging.warning('Scan thread has already stopped')
# #                 raise RuntimeError('Scan thread has already stopped')
#             else:
#                 raise RuntimeError('Thread is running where no thread was expected')
#         if self.scan_thread is not None:
# 
#             def stop_thread():
#                 logging.warning('Scan timeout after %.1f second(s)' % timeout)
#                 self.stop_thread_event.set()
#                 self.scan_aborted = True
# 
#             timeout_timer = Timer(timeout, stop_thread)  # could also use shed.scheduler() here
#             if timeout:
#                 timeout_timer.start()
#             try:
#                 while self.scan_thread.is_alive() and not self.stop_thread_event.wait(1):
#                     pass
#             except IOError:  # catching "IOError: [Errno4] Interrupted function call" because of wait_timeout_event.wait()
#                 logging.exception('Event handler problems?')
#                 raise
# 
#             timeout_timer.cancel()
#             signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler
#             self.stop_thread_event.set()
# 
#             self.scan_thread.join()  # SIGINT will be suppressed here
#             self.scan_thread = None
#         self.use_thread = None

    def start_prim_list(self):
        for scan in self.prim_list:
            if isinstance(scan, collections.Iterable):
                if len(scan) == 1:
                    self.scan = scan[0](dut=self.dut, readout=self.readout, register=self.register, register_utils=self.register_utils)
                    self.start()
                elif len(scan) == 2:
                    self.scan = scan[0](dut=self.dut, readout=self.readout, register=self.register, register_utils=self.register_utils, **scan[1])
                    self.start(**scan[1])
            else:
                self.scan = scan(dut=self.dut, readout=self.readout, register=self.register, register_utils=self.register_utils)
                self.start()
            self.stop()
            self.scan = None

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C. Stopping scan...')
        self.scan_aborted = False
        self.stop_thread_event.set()


from functools import wraps


def set_event_when_keyboard_interrupt(_lambda):
    '''Decorator function that sets Threading.Event() when keyboard interrupt (Ctrl+C) was raised

    Parameters
    ----------
    _lambda : function
        Lambda function that points to Threading.Event() object

    Returns
    -------
    wrapper : function

    Examples
    --------
    @set_event_when_keyboard_interrupt(lambda x: x.stop_thread_event)
    def scan(self, **kwargs):
        # some code

    Note
    ----
    Decorated functions cannot be derived.
    '''
    def wrapper(f):
        @wraps(f)
        def wrapped_f(self, *f_args, **f_kwargs):
            try:
                f(self, *f_args, **f_kwargs)
            except KeyboardInterrupt:
                _lambda(self).set()
#                 logging.info('Keyboard interrupt: setting %s' % _lambda(self).__name__)
        return wrapped_f
    return wrapper


if __name__ == "__main__":
    pass
