import random
import time
import datetime
import Queue
import collections
import itertools
import os
import os.path
# import array

import numpy as np


class Timer(object):
    def __init__(self, name=None):
        self.name = name

    def __enter__(self):
        self.tstart = time.time()

    def __exit__(self, type, value, traceback):
        if self.name:
            print '[%s]' % self.name,
        print 'Elapsed: %s' % (time.time() - self.tstart)


def get_all_from_queue(Q):
    """ Generator to yield one after the others all items currently
        in the queue Q, without any waiting.
    """
    try:
        while True:
            yield Q.get_nowait()
    except Queue.Empty:
        raise StopIteration


def get_item_from_queue(Q, timeout=0.01):
    """ Attempts to retrieve an item from the queue Q. If Q is
        empty, None is returned.

        Blocks for 'timeout' seconds in case the queue is empty,
        so don't use this method for speedy retrieval of multiple
        items (use get_all_from_queue for that).
    """
    try:
        item = Q.get(True, 0.01)
    except Queue.Empty:
        return None

    return item


def flatten(iterables):
    """ Flatten an iterable of iterables. Returns a generator.

        list(flatten([[2, 3], [5, 6]])) => [2, 3, 5, 6]
    """
    return (elem for iterable in iterables for elem in iterable)


def argmin_list(seq, func):
    """ Return a list of elements of seq[i] with the lowest
        func(seq[i]) scores.
        >>> argmin_list(['one', 'to', 'three', 'or'], len)
        ['to', 'or']
    """
    best_score, best = func(seq[0]), []
    for x in seq:
        x_score = func(x)
        if x_score < best_score:
            best, best_score = [x], x_score
        elif x_score == best_score:
            best.append(x)
    return best


def argmin_random_tie(seq, func):
    """ Return an element with lowest func(seq[i]) score; break
        ties at random.
    """
    return random.choice(argmin_list(seq, func))


def argmin(seq, func):
    """ Return an element with lowest func(seq[i]) score; tie goes
        to first one.
        >>> argmin(['one', 'to', 'three'], len)
        'to'
    """
    return min(seq, key=func)


def argmax_list(seq, func):
    """ Return a list of elements of seq[i] with the highest
        func(seq[i]) scores.
        >>> argmax_list(['one', 'three', 'seven'], len)
        ['three', 'seven']
    """
    return argmin_list(seq, lambda x: -func(x))


def argmax_random_tie(seq, func):
    """ Return an element with highest func(seq[i]) score; break
        ties at random.
    """
    return random.choice(argmax_list(seq, func))


def argmax(seq, func):
    """ Return an element with highest func(seq[i]) score; tie
        goes to first one.
        >>> argmax(['one', 'to', 'three'], len)
        'three'
    """
    return max(seq, key=func)


def convert_to_int(n):
    try:
        return int(n)
    except ValueError:
        return None


def convert_to_float(n):
    try:
        return float(n)
    except ValueError:
        return None


def find_key(dictionary, val):
    return [k for k, v in dictionary.iteritems() if v == val][0]


def find_keys(dictionary, val):
    return [k for k, v in dictionary.iteritems() if v == val]


def find_key_with_match(dictionary, val):
    return [k for k, v in dictionary.iteritems() if v in val][0]


def int_to_bin(n):
    return [int(digit) for digit in bin(n)[2:]]  # [2:] to chop off the "0b" part


def string_is_binary(string):
    try:
        int(string, 2)
        return True
    except (TypeError, ValueError):
        return False


def bitvector_to_bytearray(bitvector, pad_to_n_bytes=4):
    pieces = []
    pad_to_n_bits = 8 * pad_to_n_bytes
    bit_string = str(bitvector).ljust(((bitvector.length() + (pad_to_n_bits - 1)) / pad_to_n_bits) * pad_to_n_bits, "0")  # right padding zeroes
    # bitvector.pad_from_right(pad_to_n_bits-bitvector.length()%pad_to_n_bits)
    # bit_string = str(bitvector)
    for i in range(0, len(bit_string), 8):
        byte = int(bit_string[i: i + 8], 2)
        pieces.append(byte)
    # array.array('B', [17, 24, 121, 1, 12, 222, 34, 76])
    # struct.pack('B' * len(integers), *integers)
    return bytearray(pieces)


def bitvector_to_array(bitvec):
    bs = np.fromstring(bitvec.vector, dtype=np.uint8)
    bs = (bs * 0x0202020202 & 0x010884422010) % 1023
    return bs.astype(np.uint8).tostring()
#     bs = array.array('B', bitvec.vector.tostring())  # no padding needed here, replaces bitvector.getTextFromBitVector()
#     bitstream_swap = ''
#     lsbits = lambda b: (b * 0x0202020202 & 0x010884422010) % 1023
#     for b in bs:
#         bitstream_swap += chr(lsbits(b))
#     return bitstream_swap


def bitarray_to_array(bitarr):
    bs = np.fromstring(bitarr.tobytes(), dtype=np.uint8)  # byte padding happens here, bitarray.tobytes()
    bs = (bs * 0x0202020202 & 0x010884422010) % 1023
    return bs.astype(np.uint8).tostring()


def list_intersection(list_1, list_2):
    """intersection of lists

    equivalent to set.intersection

    """
    return [i for i in list_1 if i in list_2]


def flatten_iterable(iterable):
    """flatten iterable, but leaves out strings

    [[[1, 2, 3], [4, 5]], 6] -> [1, 2, 3, 4, 5, 6]

    """
    for item in iterable:
        if isinstance(item, collections.Iterable) and not isinstance(item, basestring):
            for sub in flatten_iterable(item):
                yield sub
        else:
            yield item


def iterable(item):
    """generate iterable from item, but leaves out strings

    """
    if isinstance(item, collections.Iterable) and not isinstance(item, basestring):
        return item
    else:
        return [item]

# # {{{ http://code.activestate.com/recipes/285264/ (r1)
# ---------------------------------------------------------
# natsort.py: Natural string sorting.
# ---------------------------------------------------------

# By Seo Sanghyeon.  Some changes by Connelly Barnes.


def try_int(s):
    "Convert to integer if possible."
    try:
        return int(s)
    except Exception:
        return s


def natsort_key(s):
    "Used internally to get a tuple by which s is sorted."
    import re
    return map(try_int, re.findall(r'(\d+|\D+)', s))


def natcmp(a, b):
    "Natural string comparison, case sensitive."
    return cmp(natsort_key(a), natsort_key(b))


def natcasecmp(a, b):
    "Natural string comparison, ignores case."
    return natcmp(a.lower(), b.lower())


def natsort(seq, cmp=natcmp):
    "In-place natural string sort."
    seq.sort(cmp)


def natsorted(seq, cmp=natcmp):
    "Returns a copy of seq, sorted by natural string sort."
    import copy
    temp = copy.copy(seq)
    natsort(temp, cmp)
    return temp
# # end of http://code.activestate.com/recipes/285264/ }}}


def get_iso_time():
    '''returns time as ISO string, mapping to and from datetime in ugly way

    convert to string with str()
    '''
    t1 = time.time()
    t2 = datetime.datetime.fromtimestamp(t1)
    t4 = t2.__str__()
    try:
        t4a, t4b = t4.split(".", 1)
    except ValueError:
        t4a = t4
        t4b = '000000'
    t5 = datetime.datetime.strptime(t4a, "%Y-%m-%d %H:%M:%S")
    ms = int(t4b.ljust(6, '0')[:6])
    return t5.replace(microsecond=ms)


def get_float_time():
    '''returns time as double precision floats - Time64 in pytables - mapping to and from python datetime's

    '''
    t1 = time.time()
    t2 = datetime.datetime.fromtimestamp(t1)
    return time.mktime(t2.timetuple()) + 1e-6 * t2.microsecond


def split_seq(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))


def str2bool(value):
    try:
        if value.lower() in ("yes", "y", "true", "t", "1"):
            return True
        elif value.lower() in ("no", "n", "false", "f", "0"):
            return False
        raise ValueError('Cannot convert to boolean: unknown string %s' % value)
    except AttributeError:  # not a string
        return bool(value)


def groupby_dict(dictionary, key):
    ''' Group dict of dicts by key.
    '''
    return dict((k, list(g)) for k, g in itertools.groupby(sorted(dictionary.keys(), key=lambda name: dictionary[name][key]), key=lambda name: dictionary[name][key]))


def dict_compare(d1, d2):
    '''Comparing two dictionaries.

    Note: https://stackoverflow.com/questions/4527942/comparing-two-dictionaries-in-python
    '''
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    intersect_keys = d1_keys.intersection(d2_keys)
    added = d1_keys - d2_keys
    removed = d2_keys - d1_keys
    modified = {o: (d1[o], d2[o]) for o in intersect_keys if d1[o] != d2[o]}
    same = set(o for o in intersect_keys if d1[o] == d2[o])
    return added, removed, modified, same


def zip_nofill(*iterables):
    '''Zipping iterables without fillvalue.

    Note: https://stackoverflow.com/questions/38054593/zip-longest-without-fillvalue
    '''
    return (tuple([entry for entry in iterable if entry is not None]) for iterable in itertools.izip_longest(*iterables, fillvalue=None))


def find_file_dir_up(filename, path=None, n=None):
    '''Finding file in directory upwards.
    '''
    if path is None:
        path = os.getcwd()
    i = 0
    while True:
        current_path = path
        for _ in range(i):
            current_path = os.path.split(current_path)[0]
        if os.path.isfile(os.path.join(current_path, filename)):  # found file and return
            return os.path.join(current_path, filename)
        elif os.path.dirname(current_path) == current_path:  # root of filesystem
            return
        elif n is not None and i == n:
            return
        else:  # file not found
            i += 1
            continue
