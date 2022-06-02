import pandas as pd
from datasource import Datasource

GEOFABRICK = "https://download.geofabrik.de/index-v1-nogeom.json"
BBBIKE = "https://raw.githubusercontent.com/wosch/bbbike-world/world/etc/cities.csv"


class OSM_datasource(Datasource):
    """
    a Datasource to get osm pbf files from names, extracted from GeoFabrik or BBBike

    see www.geofabrik.de and www.bbbike.org
    """

    def __init__(self):
        super().__init__(
            content="Openstreetmap data in pbf format, https://wiki.openstreetmap.org/wiki/PBF_Format",
            license="https://www.openstreetmap.org/copyright/en",
            content_url=["www.geofabrik.de", "www.bbbike.org"],
            places=True,
            file_ext=".osm.pbf"
        )

        geofabrick_urls = self._parse_geofabrik()
        bbbike_urls = self._parse_bbbike()

        # add content from bbbike if not in geofabrick
        for k, v in bbbike_urls.items():
            if k not in geofabrick_urls:
                geofabrick_urls[k] = v

        self._urls = geofabrick_urls

        return None

    def _parse_geofabrik(self):
        json = pd.json_normalize(pd.read_json(GEOFABRICK)["features"])
        json = json[["properties.name", "properties.urls.pbf"]]
        json = json.rename(columns={"properties.name": "name", "properties.urls.pbf": "url"})

        json = json.set_index("name")["url"].to_dict()

        # convert url to list of url

        urls = {k: [v] for k, v in json.items()}

        return urls

    def _parse_bbbike(self):
        sources = pd.read_csv(
            BBBIKE, sep=":", header=None, skiprows=5, usecols=[0], names=["place"]
        )[:-8]
        urls = {
            n: ["https://download.bbbike.org/osm/bbbike/" + n + "/" + n + ".osm.pbf"]
            for n in sources["place"].to_list()
        }
        return urls

    # subclass functions

    def valid_names(self):
        return list(self._urls.keys())

    def _get_url(self, data_type, place):

        if isinstance(place, str):
            return self._urls[place]
        elif isinstance(place, list):
            return {pl: self._urls[pl] for pl in place}
        else:
            raise ValueError("place must be a string or a list")