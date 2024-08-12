"""
osmdatapy
A fast and simple way to parse OSM data from pbf files into Pandas Dataframes
"""


from setuptools import setup
from Cython.Build import cythonize
import numpy

setup(
    ext_modules = cythonize("./osmdatapy/protobuf.pyx", include_path = [numpy.get_include()])
)

"""
import builtins
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext as _build_ext


# import Cython if available
try:
    from Cython.Build import cythonize
    from Cython.Distutils import build_ext as _build_ext

    USE_CYTHON = True
except ImportError:
    USE_CYTHON = False

ext = ".pyx" if USE_CYTHON else ".c"
ext_modules = [Extension("osmdatapy.protobuf", ["osmdatapy/protobuf" + ext])]

if USE_CYTHON:
    from Cython.Build import cythonize

    ext_modules = cythonize(ext_modules, compiler_directives={"language_level": "3"})


build_ext = None


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
"""