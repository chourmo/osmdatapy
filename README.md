osmdatapy
==============================
[//]: # (Badges)
[![GitHub Actions Build Status](https://github.com/REPLACE_WITH_OWNER_ACCOUNT/osmdatapy/workflows/CI/badge.svg)](https://github.com/chourmo/osmdatapy/actions?query=workflow%3ACI)
[![codecov](https://codecov.io/gh/REPLACE_WITH_OWNER_ACCOUNT/osmdatapy/branch/master/graph/badge.svg)](https://codecov.io/gh/chourmo/osmdatapy/branch/master)


A fast and simple to parse OSM data from pbf files into Pandas Dataframes

This package is a work in progress

## Features

. Quickly create an OSM object from a pbf file
. Complex queries objects : simultaneous keep and exclude tags
. Default queries for buildings, highways, pois
. Return a Dataframe, with optional geometry (GeoDataFrame)
. Optionaly extract topology for highways (source and target node ids, cut geometries at intersections)
. Minimal dependencies : numpy, pandas, geopandas, pygeos
. High performance and minimal memory footprint with a custom numpy protocolbuffer parser


## Usage

1. Download a pdf file from the two main sources of OSM extracts : 
	- BBBike (http://bbbike.org)
	- GeoFabrik (http://geofabrik.de)
	
2. Parse into an osm object and set geometry and osm type caches
3. Create a Query object from scratch or use default queries
4. Customize queries 
5. Apply query to the osm object


### Copyright

Copyright (c) 2022, chourmo


#### Acknowledgements
 
Project based on the 
[Computational Molecular Science Python Cookiecutter](https://github.com/molssi/cookiecutter-cms) version 1.6.
