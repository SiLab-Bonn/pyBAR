import logging
from yaml import safe_load
import datetime
import os
import re
import collections
from threading import Lock, Thread
# from multiprocessing import dummy as multiprocessing
import sys
import functools
import traceback
import signal
import abc
from importlib import import_module
from inspect import getmembers
from functools import partial
from ast import literal_eval


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
            with open(os.path.join(self.working_dir, "run" + ".cfg"), 'a+') as f:
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
                except Exception:
                    exc[0] = True
                    exc[1] = sys.exc_info()
                    logging.error("RunThread has thrown an exception:\n%s" % (traceback.format_exc()))
#                 finally:
#                     wait_event.set()

            worker_thread = Thread(target=worker_func, name=thread_name if thread_name else None)
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
            Configuration for the run(s).
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
        self._current_run = None

    @staticmethod
    def open_conf(conf):
        if not conf:
            return {}
        elif isinstance(conf, basestring):  # parse the first YAML document in a stream
            stream = open(conf)
            return safe_load(stream)
        elif isinstance(conf, file):  # parse the first YAML document in a stream
            return safe_load(conf)
        else:  # conf is already a dict
            return conf

    @staticmethod
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
            return run()

        return run_run_in_thread()

    def run_primlist(self, primlist, skip_remaining=False):
        '''Runs runs from a primlist.

        Parameters
        ----------
        primlist : string
            Filename of primlist.
        skip_remaining : bool
            If True, skip remaining runs, if a run does not exit with status FINISHED.
        '''
        runlist = self.open_primlist(primlist)
        for index, run in enumerate(runlist):
            @thunkify('RunThread')
            def run_run_in_thread():
                return run()
            join = run_run_in_thread()
            self._current_run = run
            logging.info('Running run %i/%i. Press Ctrl-C to stop run' % (index + 1, len(runlist)))
            signal.signal(signal.SIGINT, self._signal_handler)
            status = join()
            signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler
            self._current_run = None
            if skip_remaining and not status == RunStatus.finished:
                logging.error('Exited run %i with status %s: Skipping all remaining runs.' % (run.run_number, status))
                break

    def open_primlist(self, primlist):
        def isrun(item, module):
            return isinstance(item, RunBase.__metaclass__) and item.__module__ == module

        if isinstance(primlist, basestring):
            with open(primlist, 'r') as f:
                f.seek(0)
                srun_list = []
                for line in f.readlines():
                    line = line.strip()
                    scan_configuration = {}
                    parts = re.split('\s*[;]\s*', line)  # TODO: do not split list, dict
                    try:
                        mod = import_module(parts[0])  # points to module
                    except ImportError:
                        mod = import_module(parts[0].rsplit('.', 1)[0])  # points to class
                        islocalrun = partial(isrun, module=parts[0].split('.')[-2])
                        clsmembers = getmembers(mod, islocalrun)
                        run_cls = None
                        for cls in clsmembers:
                            if cls[0] == parts[0].rsplit('.', 1)[1]:
                                run_cls = cls[1]
                                break
                        if not run_cls:
                            raise ValueError('Found no matching class: %s' % parts[0].rsplit('.', 1)[1])
                    else:
                        islocalrun = partial(isrun, module=parts[0])
                        clsmembers = getmembers(mod, islocalrun)
                        if len(clsmembers) > 1:
                            raise ValueError('Found more than one matching class.')
                        elif not len(clsmembers):
                            raise ValueError('Found no matching class.')
                        run_cls = clsmembers[0][1]
                    for param in parts[1:]:
                        key, value = re.split('\s*[=]\s*', param)  # TODO: do not split dict
                        scan_configuration[key] = literal_eval(value)
                    if 'scan_configuration' in self.conf:
                        raise ValueError('Scan configuration taken from primlist. Configuration file must not contain scan configuration.')
                    srun_list.append(run_cls(scan_configuration=scan_configuration, **self.conf))
            return srun_list
        else:
            AttributeError('Primlist format not supported.')

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        self._current_run.abort(msg='Pressed Ctrl-C')


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
