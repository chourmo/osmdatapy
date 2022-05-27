osmdatapy
==============================
[//]: # (Badges)
[![GitHub Actions Build Status](https://github.com/chourmo/osmdatapy/workflows/CI/badge.svg)](https://github.com/chourmo/osmdatapy/actions?query=workflow%3ACI)
[![codecov](https://codecov.io/gh/chourmo/osmdatapy/branch/master/graph/badge.svg)](https://codecov.io/gh/chourmo/osmdatapy/branch/master)


A fast and simple way to parse OpenStreetMap data from pbf files into Pandas Dataframes


## Description

**Osmdatapy** focuses on performance and minimal memory use with a custom cython-based protobuf parser and optimal caching. A regional OSM .pbf of a few hundred MB disk size can be opened and analysed with a 16 GB laptob in a few milliseconds.

**Osmdatapy** provides advanced query capabilities through a reusable and composable Query object. Queries can :
	- select osm types (node, way or relation)
	- exclude and keep specific osm key:values pairs,
	- filter all osm object with a key (e.g. highway)
	- find specific id values for points and relations

**Osmdatapy** provides default queries for highways, buildings and pois.

**Osmdatapy** creates dataframes, or geodataframes, with optional topology source-target columns (only highways). The topology is preserved (one osmid value may exist in several rows if a highways has multiple crossings).

**Osmdatapy** tries to produce valid geometries even for complex relations. Relations with multiple inner and outer ways are **not currently supported**.

## Usage

1. Download a pdf file from the two main sources of OSM extracts : 
	- BBBike (http://bbbike.org)
	- GeoFabrik (http://geofabrik.de)
	
2. Open file in a osm object : osm = osmdatapy.OSM(filepath)
3. optionaly extract content statistics from osm file : osm.info()
3. Create a Query object from scratch (osmdatapy.Query) with optional defauls (osmdatapy.Query('buildings'))
4. Customize queries (e.g. query.append_exclude({"area"=:["yes"]}))
5. Apply query to the osm object : osm.query(query)

### Documentation

Documentation is available at (http://http://osmdatapy.readthedocs.io/)

### Copyright

Copyright (c) 2022, chourmo


#### Acknowledgements
 
Project based on the 
[Computational Molecular Science Python Cookiecutter](https://github.com/molssi/cookiecutter-cms) version 1.6.
