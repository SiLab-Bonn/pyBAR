import logging
from yaml import safe_load
import datetime
import os
import re
import collections
from threading import Lock, Thread, Event
# from multiprocessing import dummy as multiprocessing
import sys
import functools
import traceback
import signal
import abc
from importlib import import_module
from inspect import getmembers, isclass
from functools import partial
from ast import literal_eval


_RunStatus = collections.namedtuple('RunStatus', ['running', 'finished', 'aborted', 'crashed'])
run_status = _RunStatus(running='RUNNING', finished='FINISHED', aborted='ABORTED', crashed='CRASHED')


class RunAborted(Exception):
    pass


class RunBase():
    __metaclass__ = abc.ABCMeta

    def __init__(self, working_dir, conf, run_conf):
        """Initialize object."""
        self._working_dir = working_dir
        self._conf = conf
        self._run_conf = run_conf
        self._run_number = None
        self._run_status = None
        self.file_lock = Lock()
        self.stop_run = Event()

    def __call__(self):
        self.stop_run.clear()
        self.init()
        try:
            if self.stop_run.is_set():
                raise RunAborted('Run aborted during initialization.')
            self.run()
        except RunAborted as e:
            self._run_status = run_status.aborted
            logging.warning('Aborting run %s: %s' % (self.run_number, e))
        except Exception as e:
            self._run_status = run_status.crashed
            logging.error('Exception during run %s: %s' % (self.run_number, traceback.format_exc()))
            with open(os.path.join(self.working_dir, "crash" + ".log"), 'a+') as f:
                f.write('-------------------- Run %i --------------------\n' % self.run_number)
                traceback.print_exc(file=f)
                f.write('\n')
        else:
            self._run_status = run_status.finished
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
        self._run_status = run_status.running
        self._write_run_number()
        logging.info('Starting run %d in %s' % (self.run_number, self.working_dir))

    @abc.abstractmethod
    def run(self):
        """The run."""
        pass

    def cleanup(self):
        """Cleanup after a new run."""
        self._write_run_status(self.run_status)
        if self.run_status == run_status.finished:
            log_status = logging.INFO
        elif self.run_status == run_status.aborted:
            log_status = logging.WARNING
        else:
            log_status = logging.ERROR
        logging.log(log_status, 'Stopped run %d in %s with status %s' % (self.run_number, self.working_dir, self.run_status))

    def stop(self):
        """Stopping a run."""
        self.stop_run.set()

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
            self._run_number = 1
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

            def thunk(timeout=None):
                worker_thread.join(timeout=timeout)
#                 wait_event.wait()
                if worker_thread.is_alive():
                    return
                if exc[0]:
                    raise exc[1][0], exc[1][1], exc[1][2]
                return result[0]

            worker_thread.start()
#             threading.Thread(target=worker_func, name=thread_name if thread_name else None).start()
            return thunk
        return thunked
    return actual_decorator


class RunManager(object):
    def __init__(self, conf, working_dir=None):
        '''Run Manager is taking care of initialization and execution of runs.

        Parameters
        ----------
        conf : str, dict, file
            Configuration for the run(s). Configuration will be passed to all scans.
        working_dir : str
            Run working directory. If empty or None, working directory will be deduced from configuration.
        '''
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True

            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)

        self.working_dir = working_dir
        self.conf = conf
        self._current_run = None
        self._conf_path = None
        self.init(conf)

    def init(self, conf):
        if isinstance(conf, basestring):
                self._conf_path = conf
        elif isinstance(conf, file):
            self._conf_path = conf.name
        else:
            self._conf_path = None
        self.conf = self.open_conf(conf)
        if not self.working_dir and 'working_dir' in self.conf:
            if self._conf_path and not os.path.abspath(self.conf['working_dir']):
                self.working_dir = os.path.join(os.path.dirname(self._conf_path), self.conf.pop('working_dir'))
            else:
                self.working_dir = self.conf.pop('working_dir')
        elif self.working_dir:
            if 'working_dir' in self.conf:
                raise ValueError('Working directory is given in multiple locations')
            elif self._conf_path and not os.path.abspath(self.working_dir):
                self.working_dir = os.path.join(os.path.dirname(self._conf_path), self.working_dir)
            else:
                pass
        elif self._conf_path:
            self.working_dir = os.path.dirname(self._conf_path)
        else:
            raise ValueError('Cannot deduce working directory from configuration')

    def open_conf(self, conf):
        conf_dict = {}
        if not conf:
            pass
        elif isinstance(conf, basestring):  # parse the first YAML document in a stream
            with open(conf, 'r') as f:
                conf_dict.update(safe_load(f))
        elif isinstance(conf, file):  # parse the first YAML document in a stream
            conf_dict.update(safe_load(conf))
        else:  # conf is already a dict
            conf_dict.update(conf)
        return conf_dict

    def stop_current_run(self):
        try:
            self._current_run.stop()
        except AttributeError:
            pass

    def run_run(self, run, run_conf=None):
        '''Runs a run in another thread. Non-blocking.

        Parameters
        ----------
        run : class, object
            Run class.
        run_conf : str, dict, file
            Specific configuration for the run.

        Returns
        -------
        Function, which blocks when called, waits for the end of the run, and returns run status.
        '''
        if isclass(run):
            run = run(working_dir=self.working_dir, conf=self.conf, run_conf=self.open_conf(run_conf))
        elif run_conf:
            raise ValueError('Run object already initialized. Run configuration cannot be passed.')

        @thunkify('RunThread')
        def run_run_in_thread():
            return run()

        self._current_run = run
        return run_run_in_thread()

    def run_primlist(self, primlist, skip_remaining=False):
        '''Runs runs from a primlist.

        Parameters
        ----------
        primlist : string
            Filename of primlist.
        skip_remaining : bool
            If True, skip remaining runs, if a run does not exit with status FINISHED.

        Note
        ----
        Primlist is a text file of the following format (comment line by adding '#'):
        <module name (containing class) or class (in either case use dot notation)>; <scan parameter>=<value>; <another scan parameter>=<another value>
        '''
        runlist = self.open_primlist(primlist)
        for index, run in enumerate(runlist):
            join = self.run_run(run)
            self._current_run = run
            logging.info('Running run %i/%i. Press Ctrl-C to stop run' % (index + 1, len(runlist)))
            signal.signal(signal.SIGINT, self._signal_handler)
            status = join()
            signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler
            self._current_run = None
            if skip_remaining and not status == run_status.finished:
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
                    line = line.partition('#')[0].strip()
                    if not line:
                        continue
                    run_conf = {}
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
                        run_conf[key] = literal_eval(value)
                    srun_list.append(run_cls(working_dir=self.working_dir, conf=self.conf, run_conf=run_conf))
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
