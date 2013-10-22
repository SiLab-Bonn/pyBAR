from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
import numpy as np

extensions = [Extension("data_interpreter",["data_interpreter.pyx"]),
              Extension("data_histograming",["data_histograming.pyx"]),
              Extension("data_clusterizer",["data_clusterizer.pyx"])
              ]

setup(name='RawDataInterpreter',
      version='1.0',
      description='ATLAS FE-I4 raw data interpreter.',
      long_description='Interprets the FE-I4 raw data words and build hits in an event structure. It also checks the data integrity and creates histograms showing the event errors,trigger errors and service records.',
      author='David-Leon Pohl',
      author_email='david-leon.pohl@cern.ch',
      url='https://silab-redmine.physik.uni-bonn.de/projects/pybar',
      ext_modules = cythonize(extensions),
      include_dirs = [np.get_include()],#
      language="c++",
      )

#check compilation/installation
hits = np.empty((1,), dtype= 
        [('eventNumber', np.uint32), 
         ('triggerNumber',np.uint32),
         ('relativeBCID',np.uint8),
         ('LVLID',np.uint16),
         ('column',np.uint8),
         ('row',np.uint16),
         ('tot',np.uint8),
         ('BCID',np.uint16),
         ('triggerStatus',np.uint8),
         ('serviceRecord',np.uint32),
         ('eventStatus',np.uint8)
         ])

try:
    from data_interpreter import PyDataInterpreter
    interpreter = PyDataInterpreter()
    if(interpreter.get_hit_size() != hits.itemsize):
        print "STATUS: FAILED. Please report to pohl@physik.uni-bonn.de"
    else:
        print "STATUS: SUCCESS!"
except:
    print "STATUS: FAILED (IMPORT)"