from distutils.core import setup
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from Cython.Build import cythonize
import numpy as np

import os
path = os.getcwd()  # current path

copt = {'msvc': ['-I' + os.path.join(path, 'external')]}
lopt = {}


class build_ext_opt(build_ext):
    def build_extensions(self):
        c = self.compiler.compiler_type
        if c in copt:
            for e in self.extensions:
                e.extra_compile_args = copt[c]
        if c in lopt:
            for e in self.extensions:
                e.extra_link_args = lopt[c]
        # new-style class
        #super(build_ext_opt, self).build_extensions()
        # old-style class
        build_ext.build_extensions(self)


extensions = [Extension("data_interpreter", ["data_interpreter.pyx"]),
              Extension("data_histograming", ["data_histograming.pyx"]),
              Extension("data_clusterizer", ["data_clusterizer.pyx"]),
              Extension("analysis_functions", ["analysis_functions.pyx"])
              ]

setup(name='RawDataInterpreter',
      version='1.0',
      description='ATLAS FE-I4 raw data interpreter.',
      long_description='Interprets the FE-I4 raw data words and build hits in an event structure. It also checks the data integrity and creates histograms showing the event errors,trigger errors and service records.',
      author='David-Leon Pohl',
      author_email='david-leon.pohl@cern.ch',
      url='https://silab-redmine.physik.uni-bonn.de/projects/pybar',
      ext_modules=cythonize(extensions),
      include_dirs=[np.get_include()],
      cmdclass = {'build_ext': build_ext_opt},
      #language="c++",
      )

#check compilation/installation/data in memory alignement
hits = np.empty((1,), dtype=
        [('eventNumber', np.uint64),
         ('triggerNumber', np.uint32),
         ('relativeBCID', np.uint8),
         ('LVLID', np.uint16),
         ('column', np.uint8),
         ('row', np.uint16),
         ('tot', np.uint8),
         ('BCID', np.uint16),
         ('TDC', np.uint16),
         ('triggerStatus', np.uint8),
         ('serviceRecord', np.uint32),
         ('eventStatus', np.uint16)
         ])

try:
    from data_interpreter import PyDataInterpreter
    interpreter = PyDataInterpreter()
    from data_histograming import PyDataHistograming
    histogram = PyDataHistograming()
    from data_clusterizer import PyDataClusterizer
    clusterizer = PyDataClusterizer()
    if(interpreter.get_hit_size() != hits.itemsize):
        print "STATUS: FAILED. Please report to pohl@physik.uni-bonn.de"
    else:
        print "STATUS: SUCCESS!"
except Exception, e:
    print "STATUS: FAILED (%s)" % str(e)
