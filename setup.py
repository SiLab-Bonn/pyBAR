#!/usr/bin/env python

# Installing package from sources:
from setuptools import setup, find_packages
from platform import system

author = 'Jens Janssen, David-Leon Pohl'
author_email = 'janssen@physik.uni-bonn.de, pohl@physik.uni-bonn.de'

# https://packaging.python.org/guides/single-sourcing-package-version/
# Use
#     import get_distribution
#     get_distribution('package_name').version
# to programmatically access a version number.
# Also add
#     include VERSION
# MANIFEST.in
with open('VERSION') as version_file:
    version = version_file.read().strip()

# Requirements for core functionality from requirements.txt
# Also add
#     include requirements.txt
# MANIFEST.in
with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

if system() == 'Windows':
    install_requires.append('pywin32')

setup(
    name='pyBAR',
    version=version,
    description='pyBAR - Bonn ATLAS Readout in Python',
    url='https://github.com/SiLab-Bonn/pyBAR',
    license='BSD 3-Clause ("BSD New" or "BSD Simplified") License',
    long_description='PyBAR is a versatile readout and test system for the ATLAS FE-I4(A/B) pixel readout chip.\nIt uses the basil framework to access the readout hardware. PyBAR\'s FPGA firmware and host software includes support for different hardware platforms.',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=install_requires,
    packages=find_packages(),
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    package_data={'pybar': ['*.yaml',
                            '*.bit']},
    data_files=[('.', ['README.md',
                       'VERSION',
                       'LICENSE.txt',
                       'requirements.txt'])],
    platforms='any'
)
