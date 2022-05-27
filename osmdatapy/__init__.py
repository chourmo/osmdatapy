"""A fast and simple way to parse OSM data from pbf files into Pandas Dataframes"""

# Add imports here
from osm_data import OSM
from osm_query import Query

# Handle versioneer
from ._version import get_versions
versions = get_versions()
__version__ = versions['version']
__git_revision__ = versions['full-revisionid']
del get_versions, versions

from . import _version
__version__ = _version.get_versions()['version']
