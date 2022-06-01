"""
osmdatapy
A fast and simple way to parse OSM data from pbf files into Pandas Dataframes
"""
import sys
from setuptools import setup, find_packages
from setuptools.extension import Extension
import versioneer
from distutils.core import setup
from distutils.extension import Extension

import os

# Get numpy include directory without importing numpy at top level here
# from: https://stackoverflow.com/a/42163080

try:
    from Cython.setuptools import build_ext
except:
    # If we couldn't import Cython, use the normal setuptools
    # and look for a pre-compiled .c file instead of a .pyx file
    from setuptools.command.build_ext import build_ext
    ext_modules = [Extension("osmdatapy.protobuf", ["osmdatapt/protobuf.c"])]
else:
    # If we successfully imported Cython, look for a .pyx file
    ext_modules = [Extension("osmdatapy.protobuf", ["osmdatapt/protobuf.pyx"])]

class CustomBuildExtCommand(build_ext):
    """build_ext command for use when numpy headers are needed."""
    def run(self):

        # Import numpy here, only when headers are needed
        import numpy

        # Add numpy headers to include_dirs
        self.include_dirs.append(numpy.get_include())

        # Call original build_ext command
        build_ext.run(self)

short_description = "A fast and simple way to parse OSM data from pbf files into Pandas Dataframes".split("\n")[0]

# from https://github.com/pytest-dev/pytest-runner#conditional-requirement
needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

try:
    with open("README.md", "r") as handle:
        long_description = handle.read()
except:
    long_description = None

cmdclass["build_ext"] = build_ext

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
    ext_modules=ext_modules, #cythonize(os.path.join("osmdatapy", "*.pyx"), compiler_directives={"language_level": "3"}),

    # Manual control if final package is compressible or not, set False to prevent the .egg from being made
    zip_safe=False,

)
