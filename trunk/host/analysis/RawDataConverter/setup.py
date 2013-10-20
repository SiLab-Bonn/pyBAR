from distutils.core import setup
from Cython.Distutils import build_ext
from Cython.Build import cythonize
import numpy as np                           # <---- New line

setup(ext_modules = cythonize(
       "data_interpreter.pyx",            # our Cython source
       sources=["Basis.cpp", "Interpret.cpp"],  # additional source file(s)
       language="c++",             # generate C++ code
       #pyrex_gdb=True,
      ),
      include_dirs = [np.get_include()], 
      )
 
setup(ext_modules = cythonize(
       "data_histograming.pyx",            # our Cython source
       sources=["Basis.cpp", "Histogram.cpp"],  # additional source file(s)
       language="c++",             # generate C++ code
       #cython_gdb=True, # BUG: does not work right now: 
      ),
      include_dirs = [np.get_include()], 
      )

setup(ext_modules = cythonize(
       "data_clusterizer.pyx",            # our Cython source
       sources=["Basis.cpp", "Clusterizer.cpp"],  # additional source file(s)
       language="c++",             # generate C++ code
       #pyrex_gdb=True,
      ),
      include_dirs = [np.get_include()], 
      )
