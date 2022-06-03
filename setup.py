"""
osmdatapy
A fast and simple way to parse OSM data from pbf files into Pandas Dataframes
"""
import sys
import builtins
from setuptools import setup, find_packages
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext as _build_ext
import versioneer

from Cython.Build import cythonize

import os


ext_modules=cythonize(Extension("osmdatapy.protobuf", ["osmdatapy/protobuf.pyx"]),
        compiler_directives={"language_level": "3"})

class build_ext(_build_ext):
    def finalize_options(self):
        _build_ext.finalize_options(self)

        # Add numpy include dirs without importing numpy on module level.
        # derived from scikit-hep:
        # https://github.com/scikit-hep/root_numpy/pull/292

        # Prevent numpy from thinking it is still in its setup process:
        try:
            del builtins.__NUMPY_SETUP__
        except AttributeError:
            pass

        import numpy

        self.include_dirs.append(numpy.get_include())



short_description = "A fast and simple way to parse OSM data from pbf files into Pandas Dataframes".split("\n")[0]

# from https://github.com/pytest-dev/pytest-runner#conditional-requirement
needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

try:
    with open("README.md", "r") as handle:
        long_description = handle.read()
except:
    long_description = None

setup(
    # Self-descriptive entries which should always be present
    name='osmdatapy',
    author='chourmo',
    author_email='vincenttinet@mac.com',
    description=short_description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license='MIT',

    # Which Python importable modules should be included when your package is installed
    # Handled automatically by setuptools. Use 'exclude' to prevent some specific
    # subpackage(s) from being added, if needed
    packages=find_packages(),

    # Optional include package data to ship with your package
    # Customize MANIFEST.in if the general case does not suit your needs
    # Comment out this line to prevent the files from being packaged with your software
    include_package_data=False,

    # Allows `setup.py test` to work correctly with pytest
    setup_requires=[] + pytest_runner,

    # Additional entries you may want simply uncomment the lines you want and fill in the data
    url='https://github.com/chourmo/osmdatapy',  # Website
    
    # Required packages, pulls from pip if needed; do not use for Conda deployment
    install_requires=["numpy", "pandas", "geopandas>=0.10.0", "pygeos"],
    python_requires=">=3.9",          # Python version restrictions
    ext_modules=ext_modules,

    # Manual control if final package is compressible or not, set False to prevent the .egg from being made
    zip_safe=False,

)
