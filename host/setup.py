#!/usr/bin/env python

# Building:
# python setup.py build_ext
#
# Installing package from sources:
# python setup.py install
# For developers (creating a link to the sources):
# python setup.py develop
#
# Building source distribution:
# python setup.py sdist
# The generated source file is needed for installing by a tool like pip (pip install ...).


# from distutils.core import setup
from setuptools import setup
from setuptools import find_packages
from distutils.extension import Extension
from distutils.command.build_ext import build_ext
from Cython.Build import cythonize
import numpy as np
import os


copt = {'msvc': ['-Ipybar/analysis/RawDataConverter/external', '/EHsc']}  # set additional include path and EHsc exception handling for VS
lopt = {}


class build_ext_opt(build_ext):
    def initialize_options(self):
        build_ext.initialize_options(self)
#         self.force = 1  # does not work
#         self.inplace = 1
        self.compiler = 'msvc' if os.name == 'nt' else None  # in Anaconda the libpython package includes the MinGW import libraries and a file (Lib/distutils/distutils.cfg) which sets the default compiler to mingw32. Alternatively try conda remove libpython.

    def build_extensions(self):
        c = self.compiler.compiler_type
        if c in copt:
            for e in self.extensions:
                e.extra_compile_args = copt[c]
        if c in lopt:
            for e in self.extensions:
                e.extra_link_args = lopt[c]
        build_ext.build_extensions(self)


extensions = [
    Extension('pybar.analysis.RawDataConverter.data_interpreter', ['pybar/analysis/RawDataConverter/data_interpreter.pyx', 'pybar/analysis/RawDataConverter/Interpret.cpp', 'pybar/analysis/RawDataConverter/Basis.cpp']),
    Extension('pybar.analysis.RawDataConverter.data_histograming', ['pybar/analysis/RawDataConverter/data_histograming.pyx', 'pybar/analysis/RawDataConverter/Histogram.cpp', 'pybar/analysis/RawDataConverter/Basis.cpp']),
    Extension('pybar.analysis.RawDataConverter.data_clusterizer', ['pybar/analysis/RawDataConverter/data_clusterizer.pyx', 'pybar/analysis/RawDataConverter/Clusterizer.cpp', 'pybar/analysis/RawDataConverter/Basis.cpp']),
    Extension('pybar.analysis.RawDataConverter.analysis_functions', ['pybar/analysis/RawDataConverter/analysis_functions.pyx'])
]


f = open('VERSION', 'r')
version = f.readline().strip()
f.close()

author = 'Jens Janssen'
author_email = 'janssen@physik.uni-bonn.de'

setup(
    name='pyBAR',
    version=version,
    description='pyBAR: Bonn ATLAS Readout in Pyhton',
    url='https://silab-redmine.physik.uni-bonn.de/projects/pybar',
    license='BSD 3-Clause ("BSD New" or "BSD Simplified") License',
    long_description='',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=['cython', 'pySiLibUSB>=1.0.0', 'bitarray>=0.8.1', 'progressbar-latest>=2.4', 'basil>=2.0.0'],
    packages=find_packages(),  # exclude=['*.tests', '*.test']),
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    package_data={'': ['*.txt', 'VERSION'], 'docs': ['*'], 'examples': ['*'], 'pybar': ['*.yaml', '*.bit']},
    ext_modules=cythonize(extensions),
    include_dirs=[np.get_include()],
    cmdclass={'build_ext': build_ext_opt},
    platforms='any'
)
