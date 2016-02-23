#!/usr/bin/env python

# Installing package from sources:
# python setup.py install
# For developers (creating a link to the sources):
# python setup.py develop

from setuptools import setup, find_packages
from platform import system

f = open('VERSION', 'r')
version = f.readline().strip()
f.close()

author = 'Jens Janssen, David-Leon Pohl'
author_email = 'janssen@physik.uni-bonn.de, pohl@physik.uni-bonn.de'

# requirements for core functionality from requirements.txt
with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

if system() == 'Windows':
    install_requires.append('pywin32')

setup(
    name='pyBAR',
    version=version,
    description='pyBAR - Bonn ATLAS Readout in Python and C++',
    url='https://github.com/SiLab-Bonn/pyBAR',
    license='BSD 3-Clause ("BSD New" or "BSD Simplified") License',
    long_description='PyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip.\nIt uses the basil framework to access the readout hardware. PyBAR\'s FPGA firmware and host software includes support for different hardware platforms.',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=install_requires,
    packages=find_packages(),  # exclude=['*.tests', '*.test']),
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    package_data={'': ['README.*', 'VERSION'], 'docs': ['*'], 'examples': ['*'], 'pybar': ['*.yaml', '*.bit']},
    platforms='any'
)
