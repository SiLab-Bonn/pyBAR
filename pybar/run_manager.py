import logging
import datetime
import os
import re
from collections import namedtuple
from threading import Lock, Thread, Event, current_thread, _MainThread
import sys
import functools
import traceback
import signal
import abc
from contextlib import contextmanager
from importlib import import_module
from inspect import getmembers, isclass, getargspec
from functools import partial
from ast import literal_eval
from time import time
from functools import wraps

from yaml import safe_load

from pybar.utils.utils import find_file_dir_up


punctuation = '!,.:;?'


_RunStatus = namedtuple('RunStatus', ['init', 'running', 'finished', 'stopped', 'aborted', 'crashed'])
run_status = _RunStatus(init='INIT', running='RUNNING', finished='FINISHED', stopped='STOPPED', aborted='ABORTED', crashed='CRASHED')

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class RunAborted(Exception):
    pass


class RunStopped(Exception):
    pass


class RunBase(object):
    '''Basic run meta class

    Base class for run class.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, conf):
        '''Initialize object.

        Parameters
        ----------
        conf: dict
            Persistant configuration for all runs.
        run_conf : dict
            Run configuration for single run.
        '''
        self._conf = conf
        self._run_conf = None
        self._run_number = None
        self._run_status = run_status.init
        self.file_lock = Lock()
        self.stop_run = Event()  # abort condition for loops
        self.abort_run = Event()
        self._last_traceback = None
        self._run_start_time = None
        self._run_stop_time = None
        self._total_run_time = None
        self._last_error_message = None
        self._last_traceback = None
        self._cancel_functions = None
        self.connect_cancel(["abort"])

    def __getattr__(self, name):
        ''' This is called in a last attempt to receive the value for an attribute that was not found in the usual places.
        '''
        try:
            return self._run_conf[name]  # Accessing run conf parameters
        except (KeyError, TypeError):  # If key is not existing or run conf is not a dict
            raise AttributeError("'%s' has no attribute '%s'" % (self.__class__.__name__, name))

    @property
    def run_id(self):
        '''Run name without whitespace
        '''
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', self.__class__.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    @property
    def conf(self):
        '''Configuration (namedtuple)
        '''
        conf = namedtuple('conf', field_names=self._conf.keys())
        return conf(**self._conf)  # prevent changing dict

    @property
    def run_conf(self):
        '''Run configuration (namedtuple)
        '''
        run_conf = namedtuple('run_conf', field_names=self._run_conf.keys())
        return run_conf(**self._run_conf)  # prevent changing dict

    @abc.abstractproperty
    def _default_run_conf(self):
        '''Defining default run configuration (dictionary)
        '''
        pass

    @property
    def default_run_conf(self):
        '''Default run configuration (namedtuple)
        '''
        default_run_conf = namedtuple('default_run_conf', field_names=self._default_run_conf.keys())
        return default_run_conf(**self._default_run_conf)  # prevent changing dict

    @property
    def working_dir(self):
        return self._conf['working_dir']

    @property
    def run_number(self):
        return self._run_number

    @run_number.setter
    def run_number(self, value):
        raise AttributeError

    @property
    def run_status(self):
        return self._run_status

    @run_status.setter
    def run_status(self, value):
        raise AttributeError

    def get_run_status(self):
        return self._run_status

    def run(self, run_conf, run_number=None, signal_handler=None):
        self._init(run_conf, run_number)
        logging.info('Starting run %d (%s) in %s', self.run_number, self.__class__.__name__, self.working_dir)
        # set up signal handler
        if isinstance(current_thread(), _MainThread):
            logging.info('Press Ctrl-C to stop run')
            if not signal_handler:
                signal_handler = self._signal_handler
            signal.signal(signal.SIGINT, signal_handler)
        try:
            with self._run():
                self.do_run()
        except RunAborted as e:
            self._run_status = run_status.aborted
            self._last_traceback = None
            self._last_error_message = e.__class__.__name__ + ": " + str(e)
        except Exception as e:
            self._run_status = run_status.crashed
            self._last_traceback = traceback.format_exc()
            self._last_error_message = e.__class__.__name__ + ": " + str(e)
        else:
            self._run_status = run_status.finished
            self._last_traceback = None
            self._last_error_message = None
        finally:
            pass
        # revert signal handler to default
        if isinstance(current_thread(), _MainThread):
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        self._cleanup()
        # log message
        if self.run_status == run_status.finished:
            log_status = logging.INFO
        else:
            if self.run_status == run_status.stopped:
                log_status = logging.INFO
            elif self.run_status == run_status.aborted:
                log_status = logging.WARNING
            else:
                log_status = logging.ERROR
            logging.log(log_status, 'Run {} {}{}{}'.format(self.run_number, self.run_status, (': ' + str(self._last_error_message)) if self._last_error_message else '', ('\n' + self._last_traceback) if self._last_traceback else ''))
        if self._last_traceback:
            with open(os.path.join(self.working_dir, "crash" + ".log"), 'a+') as f:
                f.write('-------------------- Run {} ({}) --------------------\n'.format(self.run_number, self.__class__.__name__))
                traceback.print_exc(file=f)
                f.write('\n')
        logging.log(log_status, '{} run {} ({}) in {} (total time: {})'.format(self.run_status, self.run_number, self.__class__.__name__, self.working_dir, str(self._total_run_time)))
        return self.run_status

    def _init(self, run_conf, run_number=None):
        '''Initialization before a new run.
        '''
        self.stop_run.clear()
        self.abort_run.clear()
        self._run_status = run_status.running
        self._write_run_number(run_number)
        self._init_run_conf(run_conf)

    def _init_run_conf(self, run_conf):
        attribute_names = [key for key in self._default_run_conf.keys() if (key in self.__dict__ or (hasattr(self.__class__, key) and isinstance(getattr(self.__class__, key), property)))]
        if attribute_names:
            raise RuntimeError('Attribute names already in use. Rename the following parameters in run conf: %s' % ', '.join(attribute_names))
        sc = namedtuple('run_configuration', field_names=self._default_run_conf.keys())
        default_run_conf = sc(**self._default_run_conf)
        if run_conf:
            self._run_conf = default_run_conf._replace(**run_conf)._asdict()
        else:
            self._run_conf = default_run_conf._asdict()

    @contextmanager
    def _run(self):
        try:
            self.pre_run()
            yield
            self.post_run()
            if self.abort_run.is_set():
                raise RunAborted()
        finally:
            self.cleanup_run()

    @abc.abstractmethod
    def pre_run(self):
        '''Before run.
        '''
        pass

    @abc.abstractmethod
    def do_run(self):
        '''The run.
        '''
        pass

    @abc.abstractmethod
    def post_run(self):
        '''After run.
        '''
        pass

    @abc.abstractmethod
    def cleanup_run(self):
        '''Cleanup after run, will be executed always, even after exception. Avoid throwing exceptions here.
        '''
        pass

    def _cleanup(self):
        '''Cleanup after a new run.
        '''
        self._write_run_status(self.run_status)

    def connect_cancel(self, functions):
        '''Run given functions when a run is cancelled.
        '''
        self._cancel_functions = []
        for func in functions:
            if isinstance(func, basestring) and hasattr(self, func) and callable(getattr(self, func)):
                self._cancel_functions.append(getattr(self, func))
            elif callable(func):
                self._cancel_functions.append(func)
            else:
                raise ValueError("Unknown function %s" % str(func))

    def handle_cancel(self, **kwargs):
        '''Cancelling a run.
        '''
        for func in self._cancel_functions:
            f_args = getargspec(func)[0]
            f_kwargs = {key: kwargs[key] for key in f_args if key in kwargs}
            func(**f_kwargs)

    def stop(self, msg=None):
        '''Stopping a run. Control for loops. Gentle stop/abort.

        This event should provide a more gentle abort. The run should stop ASAP but the run is still considered complete.
        '''
        if not self.stop_run.is_set():
            if msg:
                logging.info('%s%s Stopping run...', msg, ('' if msg[-1] in punctuation else '.'))
            else:
                logging.info('Stopping run...')
        self.stop_run.set()

    def abort(self, msg=None):
        '''Aborting a run. Control for loops. Immediate stop/abort.

        The implementation should stop a run ASAP when this event is set. The run is considered incomplete.
        '''
        if not self.abort_run.is_set():
            if msg:
                logging.error('%s%s Aborting run...', msg, ('' if msg[-1] in punctuation else '.'))
            else:
                logging.error('Aborting run...')
        self.abort_run.set()
        self.stop_run.set()  # set stop_run in case abort_run event is not used

    def close(self):
        '''Close properly and releasing hardware resources.

        This should be called before Python garbage collector takes action.
        '''
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
                            if parts[2] in status:
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

    def _write_run_number(self, run_number=None):
        self._run_start_time = datetime.datetime.now()
        run_numbers = self._get_run_numbers()
        if run_number:
            self._run_number = run_number
        else:
            if not run_numbers:
                self._run_number = 1
            else:
                self._run_number = max(dict.iterkeys(run_numbers)) + 1
        run_numbers[self.run_number] = str(self.run_number) + ' ' + self.__class__.__name__ + ' ' + 'RUNNING' + ' ' + str(self._run_start_time) + '\n'
        with self.file_lock:
            with open(os.path.join(self.working_dir, "run" + ".cfg"), "w") as f:
                for value in dict.itervalues(run_numbers):
                    f.write(value)

    def _write_run_status(self, status_msg):
        self._run_stop_time = datetime.datetime.now()
        self._total_run_time = self._run_stop_time - self._run_start_time
        run_numbers = self._get_run_numbers()
        if not run_numbers:
            run_numbers[self.run_number] = str(self.run_number) + ' ' + self.__class__.__name__ + ' ' + status_msg + ' ' + str(self._run_stop_time) + ' ' + str(self._total_run_time) + '\n'
        else:
            parts = re.split('\s+', run_numbers[self.run_number])
            parts[2] = status_msg
            run_numbers[self.run_number] = ' '.join(parts[:-1]) + ' ' + str(self._run_stop_time) + ' ' + str(self._total_run_time) + '\n'
        with self.file_lock:
            with open(os.path.join(self.working_dir, "run" + ".cfg"), "w") as f:
                for value in dict.itervalues(run_numbers):
                    f.write(value)

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        self.handle_cancel(msg='Pressed Ctrl-C')


def thunkify(thread_name=None, daemon=True, default_func=None):
    '''Make a function immediately return a function of no args which, when called,
    waits for the result, which will start being processed in another thread.
    Taken from https://wiki.python.org/moin/PythonDecoratorLibrary.
    '''
    def actual_decorator(f):
        @functools.wraps(f)
        def thunked(*args, **kwargs):
            result = [None]
            exc = [False, None]  # has exception?, exception info
#             wait_event = threading.Event()

            def worker_func():
                try:
                    func_result = f(*args, **kwargs)
                    result[0] = func_result
                except Exception:
                    exc[0] = True
                    exc[1] = sys.exc_info()
                    logging.error("%s has thrown an exception:\n%s", thread_name, traceback.format_exc())
#                 finally:
#                     wait_event.set()

            worker_thread = Thread(target=worker_func, name=thread_name if thread_name else None)
            worker_thread.daemon = daemon

            def thunk(timeout=None):
                # avoid blocking MainThread
                start_time = time()
                while True:
                    worker_thread.join(timeout=1.0)
                    if (timeout and timeout < time() - start_time) or not worker_thread.is_alive():
                        break
#                 worker_thread.join(timeout=timeout)
#                 wait_event.wait()
                if worker_thread.is_alive():
                    if default_func is None:
                        return
                    else:
                        return default_func()
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
            Configuration for the run(s). Configuration will be passed to all scans.
        '''
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True

            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)

        self._conf = None  # configuration dictionary
        self.current_run = None  # current run number
        self._conf_path = None  # absolute path of the configuation file
        self.init(conf)

    @property
    def conf(self):
        '''Configuration (namedtuple)
        '''
        conf = namedtuple('conf', field_names=self._conf.keys())
        return conf(**self._conf)  # prevent changing dict

    def init(self, conf):
        # current working directory
        if isinstance(conf, basestring) and os.path.isfile(os.path.abspath(conf)):
            conf = os.path.abspath(conf)
            self._conf_path = conf
        # search directory upwards form current working directory
        elif isinstance(conf, basestring) and find_file_dir_up(conf):
            conf = find_file_dir_up(conf)
            self._conf_path = conf
        elif isinstance(conf, file):
            self._conf_path = os.path.abspath(conf.name)
        else:
            self._conf_path = None
        self._conf = self.open_conf(conf)
        if 'working_dir' in self._conf and self._conf['working_dir']:
            # dirty fix for Windows pathes
            self._conf['working_dir'] = os.path.normpath(self._conf['working_dir'].replace('\\', '/'))
            if self._conf_path and not os.path.isabs(self._conf['working_dir']):
                # if working_dir is relative path, join path to configuration file and working_dir
                self._conf['working_dir'] = os.path.join(os.path.dirname(self._conf_path), self._conf['working_dir'])
            else:
                # working_dir is absolute path, keep that
                pass
        # use path of configuration file
        elif self._conf_path:
            self._conf['working_dir'] = os.path.dirname(self._conf_path)
        else:
            raise ValueError('Cannot deduce working directory from configuration')
        logging.info('Using working directory %s', self._conf['working_dir'])

    def close(self):
        if self.current_run is not None:
            self.current_run.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    @staticmethod
    def open_conf(conf):
        conf_dict = {}
        if not conf:
            pass
        elif isinstance(conf, basestring):  # parse the first YAML document in a stream
            if os.path.isfile(os.path.abspath(conf)):
                logging.info('Loading configuration from file %s', os.path.abspath(conf))
                with open(os.path.abspath(conf), 'r') as f:
                    conf_dict.update(safe_load(f))
            else:  # YAML string
                try:
                    conf_dict.update(safe_load(conf))
                except ValueError:  # invalid path/filename
                    raise IOError("File not found: %s" % os.path.abspath(conf))
                else:
                    logging.info('Loading configuration from file %s', os.path.abspath(conf.name))
        elif isinstance(conf, file):  # parse the first YAML document in a stream
            conf_dict.update(safe_load(conf))
        else:  # conf is already a dict
            conf_dict.update(conf)
        return conf_dict

    def cancel_current_run(self, msg=None):
        '''Control for runs.
        '''
        self.current_run.handle_cancel(msg=msg)

    def run_run(self, run, conf=None, run_conf=None, use_thread=False, catch_exception=True):
        '''Runs a run in another thread. Non-blocking.

        Parameters
        ----------
        run : class, object
            Run class or object.
        run_conf : str, dict, file
            Specific configuration for the run.
        use_thread : bool
            If True, run run in thread and returns blocking function.

        Returns
        -------
        If use_thread is True, returns function, which blocks until thread terminates, and which itself returns run status.
        If use_thread is False, returns run status.
        '''
        if isinstance(conf, basestring) and os.path.isfile(conf):
            logging.info('Updating configuration from file %s', os.path.abspath(conf))
        elif conf is not None:
            logging.info('Updating configuration')
        conf = self.open_conf(conf)
        self._conf.update(conf)

        if isclass(run):
            # instantiate the class
            run = run(conf=self._conf)

        local_run_conf = {}
        # general parameters from conf
        if 'run_conf' in self._conf:
            logging.info('Updating run configuration using run_conf key from configuration')
            local_run_conf.update(self._conf['run_conf'])
        # check for class name, scan specific parameters from conf
        if run.__class__.__name__ in self._conf:
            logging.info('Updating run configuration using %s key from configuration' % (run.__class__.__name__,))
            local_run_conf.update(self._conf[run.__class__.__name__])

        if isinstance(run_conf, basestring) and os.path.isfile(run_conf):
            logging.info('Updating run configuration from file %s', os.path.abspath(run_conf))
        elif run_conf is not None:
            logging.info('Updating run configuration')
        run_conf = self.open_conf(run_conf)
        # check for class name, scan specific parameters from conf
        if run.__class__.__name__ in run_conf:
            run_conf = run_conf[run.__class__.__name__]
        # run_conf parameter has highest priority, updated last
        local_run_conf.update(run_conf)

        if use_thread:
            self.current_run = run

            @thunkify(thread_name='RunThread', daemon=True, default_func=self.current_run.get_run_status)
            def run_run_in_thread():
                return run.run(run_conf=local_run_conf)

            signal.signal(signal.SIGINT, self._signal_handler)
            logging.info('Press Ctrl-C to stop run')

            return run_run_in_thread()
        else:
            self.current_run = run
            status = run.run(run_conf=local_run_conf)
            if not catch_exception and status != run_status.finished:
                raise RuntimeError('Exception occurred. Please read the log.')
            return status

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
            logging.info('Progressing with run %i out of %i...', index + 1, len(runlist))
            join = self.run_run(run, use_thread=True)
            status = join()
            if skip_remaining and not status == run_status.finished:
                logging.error('Exited run %i with status %s: Skipping all remaining runs.', run.run_number, status)
                break

    def open_primlist(self, primlist):
        def isrun(item, module):
            return isinstance(item, RunBase.__metaclass__) and item.__module__ == module  # only class from module, not from other imports

        if isinstance(primlist, basestring):
            with open(primlist, 'r') as f:
                f.seek(0)
                run_list = []
                for line in f.readlines():
                    line = line.partition('#')[0].strip()
                    if not line:
                        continue
                    parts = re.split('\s*[;]\s*', line)
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
                    if run_cls.__class__.__name__ in self._conf:
                        run_conf = self._conf[run_cls.__class__.__name__]
                    else:
                        run_conf = {}
                    for param in parts[1:]:
                        key, value = re.split('\s*[=:]\s*', param, 1)
                        run_conf[key] = literal_eval(value)
                    run_list.append(run_cls(conf=self._conf, run_conf=run_conf))
            return run_list
        else:
            AttributeError('Primlist format not supported.')

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        self.cancel_current_run(msg='Pressed Ctrl-C')


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
