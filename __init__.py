"""A fast and simple to parse OSM data from pbf files into Pandas Dataframes"""

# Add imports here
from .osmdatapy import *

# Handle versioneer
from ._version import get_versions
versions = get_versions()
__version__ = versions['version']
__git_revision__ = versions['full-revisionid']
del get_versions, versions
