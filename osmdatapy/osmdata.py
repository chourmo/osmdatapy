import os, sys
from struct import unpack

import numpy as np
import pandas as pd

from ._frame import Frame
from .osmquery import Query
from .headers import parse_header, parse_blob, parse_blockheader, parse_cache_block
from .block import parse_block


class OSM(Frame):
    """
    An OSM object storing pbf data from a file
    initated from either a a filepath or a place name

    Parameters
    ----------
    filepath : path to a pbf file

    Attributes
    ----------
    features : list of features in pbf (see PBF format on osm wiki)
    optional_features : list of optional features
    strings : list of all strings (tags, tag values, relation types)
    """

    def __init__(self, filepath):

        self.filepath = self._validate_file(filepath)
        blocks, _geo, feat, opt_feat = self._read_pbf()

        self.features = feat
        self.optional_features = opt_feat

        # set caches
        self._set_geometry_cache(_geo)
        self._set_string_cache(blocks)

    def info(self):
        "Print cached content and memory usage"

        info = []
        string_MB = 0
        MB = 1024 * 1024

        for bl in self._blocks:
            string_MB += sys.getsizeof(bl["stringtable"]) / MB

        string_MB += sys.getsizeof(self.strings) / MB
        geo_MB = (sys.getsizeof(self._geo_index) + sys.getsizeof(self._geo_coords)) / MB

        offset_MB = 0
        for t in ["node_offsets", "way_offsets", "rel_offsets"]:
            offset_MB += sum([sys.getsizeof(x[t]) / MB for x in self._blocks])

        d = sum([len(x["dense_offsets"]) > 0 for x in self._blocks])
        n = sum([len(x["node_offsets"]) > 0 for x in self._blocks])
        w = sum([len(x["way_offsets"]) > 0 for x in self._blocks])
        r = sum([len(x["rel_offsets"]) > 0 for x in self._blocks])
        info.append(
            "{0} blocks : {4} dense nodes, {1} nodes, {2} ways, {3} relations".format(
                len(self._blocks), n, w, r, d
            )
        )
        info.append('---------------------------------------')
        info.append('Cache memory usage : {0:.1f} MB'.format(geo_MB + offset_MB + string_MB))
        info.append("{0} points, {1:.1f} MB".format(len(self._geo_index), geo_MB))
        info.append("offsets : {0:.1f} MB".format(offset_MB))
        info.append('strings : {0:.1f} MB'.format(string_MB))

        print("\r\n".join(info))

    def geometry(self):
        """returns a Dataframe of point coordinates, osm ids as index"""
        cols = ["lon", "lat"]
        df = pd.DataFrame(self._geo_coords, index=self._geo_index, columns=cols)
        return df.sort_index()

    def coords(self, ids):
        """returns a numpy array of coordinates correspong to ids"""
        ix = np.searchsorted(self._geo_index, ids)
        return self._geo_coords[ix]

    def map_to_strings(self, integers):
        """map an integer Series to a string Series from cached strings"""

        stringmap = {k: self.strings[k] for k in integers.unique()}
        return integers.map(stringmap)

    # ------------------------------------------------------
    # PBF parsing and caching

    def _read_pbf(self):

        with open(self.filepath, "rb") as f:

            geoms = []
            blocks = []
            buf = f.read(4)

            while len(buf) > 0:
                msg_len = unpack("!L", buf)[0]
                datasize, blobtype = parse_header(f.read(msg_len))
                cursor = f.tell()

                st_offset, end_offset, compr, data = parse_blob(f.read(datasize))

                if blobtype == "OSMHeader":
                    feat, opt_feat = parse_blockheader(data, compr)

                elif blobtype == "OSMData":
                    pts, metadata = parse_cache_block(data, compr)
                    metadata["start_offset"] = cursor + st_offset
                    metadata["end_offset"] = cursor + end_offset
                    metadata["compression"] = compr
                    blocks.append(metadata)

                    if pts is not None:
                        geoms.append(pts)

                buf = f.read(4)

        return blocks, np.concatenate(geoms), feat, opt_feat

    def _set_geometry_cache(self, geom):
        """set geometry index and coords attributes, ensure that geometry index is sorted"""

        # sort by index and make contiguous array to speed searches
        _geo = geom[geom[:, 0].argsort()]
        self._geo_index = np.ascontiguousarray(_geo[:, 0], dtype="uint64")
        self._geo_coords = np.float32(_geo[:, 1:] / 1000000000)

    def _set_string_cache(self, blocks):
        """Parse each block strings, create local map, return updated blocks"""

        s = []
        new_blocks = []

        for block in blocks:
            s.extend(block["stringtable"])

        stringmap = list(set(s))
        s = self._string_to_pos(stringmap)

        for block in blocks:
            block["stringtable"] = np.array(
                [
                    s[block["stringtable"][pos]]
                    for pos in range(len(block["stringtable"]))
                ]
            )
            new_blocks.append(block)

        self._blocks = new_blocks
        self.strings = stringmap

    @staticmethod
    def _string_to_pos(strings):
        """Return a dict map from a string to its position in a list"""
        return dict(zip(strings, range(len(strings))))

    # ---------------------------------------------------------------
    # PBF validation

    @staticmethod
    def _validate_file(filepath):
        if not isinstance(filepath, str):
            raise ValueError("'filepath' should be a string.")
        if not filepath.endswith(".pbf"):
            raise ValueError(
                f"Input data should be in Protobuf format (*.osm.pbf). "
                f"Found: {filepath.split('.')[-1]}"
            )
        if not os.path.exists(filepath):
            raise ValueError(f"File does not exist: " f"Found: {filepath}")
        return filepath

    # -------------------------------------------------------------
    # query and dataframe creation

    def query(self, query):
        """Query osm data based on Query Object into a DataFrame or GeoDataFrame"""

        mapper = self._string_to_pos(self.strings)
        strmap = {k: mapper[k] for k in query.all_strings() if k in mapper}
        ids, tags, rels = self._process_queries(query, strmap)

        # if query relations and must be expanded for geometry
        # query ways for expansions
        # TODO : repeat until all super-relations are expanded

        if query.relations and query.geometry and len(rels[rels[:, 2] == 1]) > 0:
            rel_ways = rels[rels[:, 2] == 1][:, 1].tolist()
            query_r = Query(ways=True, way_ids=rel_ways, tags=False, keep_first=False)
            ids_w, _, ways = self._process_queries(query_r, strmap)

            ids_w = ids_w[:, 0]
            ways[:, 0] = ids_w[ways[:, 0]]
            ways = ways[:, 0:2]

        else:
            ways = None

        return self.to_dataframe(query, ids, tags, rels, ways)

    def _process_queries(self, query, strmap):

        queries = [query.block_query(bl, strmap) for bl in self._blocks]
        res = []

        with open(self.filepath, "rb") as f:

            for bl, qu in zip(self._blocks, queries):

                if qu is None:
                    continue

                f.seek(bl["start_offset"])
                data = f.read(bl["end_offset"])
                comp = bl["compression"]
                stmap = bl["stringtable"]

                res_block = parse_block(data, stmap, qu, comp)
                if res_block is not None:
                    res.extend(res_block)

        return self._merge_results(res)

    @staticmethod
    def _merge_results(res):
        """Merge list of results in a single tuple, renumber tag ids and rel ids to global positions"""

        # shift tagids and relation ids to global positions
        pos = 0
        id_res, tag_res, rel_res = [], [], []

        for ids, tags, rels in res:
            id_res.append(ids)
            if tags is not None:
                tags[:, 0] = tags[:, 0] + pos
                tag_res.append(tags)
            if rels is not None:
                rels[:, 0] = rels[:, 0] + pos
                rel_res.append(rels)
            pos += len(ids)

        if not id_res:
            return None, None, None
        if tag_res:
            tag_res = np.vstack(tag_res)
        else:
            tag_res = None
        if rel_res:
            rel_res = np.vstack(rel_res)
        else:
            rel_res = None
        return np.vstack(id_res), tag_res, rel_res