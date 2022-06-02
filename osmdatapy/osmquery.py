import copy
import numpy as np
from typing import Optional, Union

from .defaults import HIGHWAYS, BUILDINGS, POIS, NOT_AREA, IS_AREA, IS_AREA_KEY_ANY_VALUE, RELATION_AREA, RELATION_LINESTRING


class Query:
    """
    Query to pass to OSM object

    Parameters
    ----------
    defaults : name of a default query (highway, buildings, pois)
    nodes : query nodes
    ways : query ways
    relations : query relations
    must_tags: None or list of at least one tag in a result osm object
    keep : None or empty list (keep all) or dictionary of tag:list (keep pairs)
    exclude : None or empty list (drop all) or dictionary of tag:list (exclude pairs),
    keep_first: if True keep and then exclude, if False exclude except if in keep
    tags : list of result tag columns, if True return all tags else no tags
    node_ids, way_ids : get nodes and ways with ids in lists, if None, get all
    relation_type: optional relation type list of strings, cannot be an empty list
    metadata: extract versions, changeset and timestamp
    geometry : if True, add a geometry column, may be point, linestring or polygon
    topology : if True, merge segments topologically, so that points belonging to many osm objects
               are the first or last point, add a source and target column
               topology = True must be associated with geometry = True and ways = True
    """

    def __init__(
        self,
        defaults: Optional[str] = None,
        nodes: bool = False,
        ways: bool = False,
        relations: bool = False,
        must_tags: Optional[list] = None,
        keep: Optional[dict] = None,
        exclude: Optional[dict] = None,
        keep_first: bool = True,
        tags: Union[list, bool] = True,
        node_ids: Optional[list] = None,
        way_ids: Optional[list] = None,
        relation_type: Optional[list] = None,
        metadata: bool = False,
        geometry: bool = False,
        topology: bool = False,
    ):

        # simple parameters
        self.nodes = nodes
        self.ways = ways
        self.relations = relations
        self.must_tags = must_tags
        self.geometry = geometry
        self.metadata = metadata
        self.keep_first = keep_first
        self.keep = keep
        self.exclude = exclude
        self.relation_type = relation_type

        # indirect parameters with validation or conversion
        self.node_set = node_ids
        self.way_set = way_ids
        self.topology = topology
        self.tags = tags

        # replace or append defaults
        if defaults is not None:
            self.set_default(defaults)

        self._keep_excl_validator()

    def copy(self):
        return copy.copy(self)

    def set_default(self, name):
        if name == "highways":
            defaults = HIGHWAYS
        elif name == "buildings":
            defaults = BUILDINGS
        elif name == "pois":
            defaults = POIS
        else:
            raise ValueError("Default must be highways, buildings or pois")

        for k, v in defaults.items():

            if k == "tags":
                self.append_tags(v)
            elif k == "keep":
                self.append_keep(v)
            elif k == "exclude":
                self.append_exclude(v)
            elif k == "relation_type":
                self.append_relation_type(v)

            # directly set simple parameters
            else:
                setattr(self, k, v)

    @property
    def tags(self):
        return self._tags

    @tags.setter
    def tags(self, value):
        if type(value) == bool and value:  # all tags
            self._tags = None
        elif type(value) == bool:  # no tags
            self._tags = []
        else:
            self._tags = value

    @property
    def node_set(self):
        return self._node_set

    @node_set.setter
    def node_set(self, value):
        if value is None:
            self._node_set = None
        else:
            self._node_set = set(value)

    @property
    def way_set(self):
        return self._way_set

    @way_set.setter
    def way_set(self, value):
        if value is None:
            self._way_set = None
        else:
            self._way_set = set(value)

    @property
    def topology(self):
        return self._topology

    @topology.setter
    def topology(self, value):
        if value and not self.ways and not self.geometry:
            raise ValueError("Ways and geometry must be True when topology is True")
        self._topology = value

    def _keep_excl_validator(self):
        if self.keep is None and self.exclude is None:
            return None
        if self.keep_first and self.keep is None and self.exclude is not None:
            raise ValueError(
                "keep cannot be set to None if keep_first is True and exclude is not None"
            )
        if not self.keep_first and self.exclude is None and self.keep is not None:
            raise ValueError(
                "exclude cannot be set to None if keep_first is False and keep is not None"
            )

        return None

    # -------------------------------------------------------------
    # Query composition methods

    def append_tags(self, tags):
        """Append tags to the tag list, or if True, get all tags"""

        if type(tags) == bool and tags:
            self._tags = None
        elif self.tags is None:
            self._tags = tags
        else:
            self._tags = list(set(self._tags + tags))

    def append_keep(self, filter_dict):
        """Add a new filter content to the keep filter"""
        self.keep = self._append_dictionaries(self.keep, filter_dict)
        self._keep_excl_validator()

    def append_exclude(self, filter_dict):
        """Add a new filter content to the exclude filter"""
        self.exclude = self._append_dictionaries(self.exclude, filter_dict)
        # self._keep_excl_validator()

    def append_relation_type(self, type_list):
        """Add a new filter content to the relation_type filter"""
        self.relation_type = self.relation_type.extend(type_list)

    @staticmethod
    def _append_dictionaries(dict1, dict2):

        if dict1 is None and dict2 is None:
            raise ValueError("One of the dictionnaries must not be None")
        if dict1 is None:
            return dict2
        if dict2 is None:
            return dict1

        for k, v in dict2.items():
            if type(v) == list and not v:
                dict1[k] = []
            elif k in dict1.keys():
                if type(dict1[k]) == list and not dict1[k]:
                    dict1[k] = []
                else:
                    dict1[k] = list(set(dict1[k] + dict2[k]))
            else:
                dict1[k] = dict2[k]
        return dict1

    # -------------------------------------------------------------
    # integer query dictionnary internal to a block

    def all_strings(self):
        st = []
        if self.keep is not None:
            st.extend(self.keep.keys())
            st.extend([j for i in self.keep.values() for j in i])
        if self.exclude is not None:
            st.extend(self.exclude.keys())
            st.extend([j for i in self.exclude.values() for j in i])
        if self.tags is not None:
            st.extend(self.tags)
        if self.must_tags is not None:
            st.extend(self.must_tags)

        # add area strings
        for k, v in NOT_AREA.items():
            st.append(k)
            st.extend(v)
        for k, v in IS_AREA.items():
            st.append(k)
            st.extend(v)
        st.append("multipolygon")

        return set(st)

    def block_query(self, block, strmap):
        """Return a query dictionary for parsing functions matching a block string map, or None if query cannot have results for block"""

        # at least one matching osm type
        if not (
            (self.nodes and block["node_offsets"])
            or (self.ways and block["way_offsets"])
            or (self.relations and block["rel_offsets"])
        ):
            return None

        # map query strings to block local integers
        mapper = dict(zip(block["stringtable"], range(len(block["stringtable"]))))
        strmap = {k: mapper[v] for k, v in strmap.items() if v in mapper}

        q = self.as_dict()

        q["get_tags"] = self._get_tags()
        if q["get_tags"] and not strmap:
            return None

        if not q["nodes"]:
            q["node_offsets"] = []
            len(q["dense_offsets"]) ==0
        elif q["node_set"]:
            q["node_offsets"] = [
                n for n in block["node_offsets"] if n[0] in q["node_set"]
            ]
            q["dense_offsets"] = block["dense_offsets"].copy()
        else:
            q["node_offsets"] = block["node_offsets"].copy()
            q["dense_offsets"] = block["dense_offsets"].copy()

        if not q["ways"]:
            q["way_offsets"] = []
        elif q["way_set"]:
            q["way_offsets"] = [w for w in block["way_offsets"] if w[0] in q["way_set"]]
        else:
            q["way_offsets"] = block["way_offsets"].copy()

        if not q["relations"]:
            q["rel_offsets"] = []
        else:
            q["rel_offsets"] = block["rel_offsets"].copy()

        q["tags"] = set(list(self._map_list(q["tags"], strmap)))
        q["keep"], q["keep_all"] = self._map_filter(q["keep"], strmap)
        q["excl"], q["excl_all"] = self._map_filter(q["exclude"], strmap)
        q["must_tags"] = self._map_list(q["must_tags"], strmap)
        q["relation_type"] = self._map_list(q["relation_type"], strmap)

        q["no_tagval"] = (
            q["must_tags"] is None
            and q["keep"] is None
            and q["keep_all"] is None
            and q["excl"] is None
            and q["excl_all"] is None
        )

        # area tags
        q["area_no"] = self._map_area({"area": ["no"]}, strmap)
        q["is_area"] = self._map_area(IS_AREA, strmap)
        q["is_area_key"] = set(
            [strmap[k] for k in NOT_AREA.keys() if k in strmap]
            + [strmap[k] for k in IS_AREA.keys() if k in strmap]
            + [strmap[k] for k in IS_AREA_KEY_ANY_VALUE if k in strmap]
        )
        q["is_area_key_any_value"] = self._map_list(IS_AREA_KEY_ANY_VALUE, strmap)
        q["not_area"] = self._map_area(NOT_AREA, strmap)
        q["area"] = (q["is_area"]) or (q["not_area"]) or (q["is_area_key"])
        q["rel_area"] = self._map_list(RELATION_AREA, strmap)
        q["rel_line"] = self._map_list(RELATION_LINESTRING, strmap)

        # if query cannot have results, return None
        c1 = (q["must_tags"] is not None) and (
            len(q["must_tags"]) != len(self.must_tags)
        )
        c2 = (
            self.keep is not None
            and not q["keep"]
            and (self.exclude is None or not self.keep_first)
        )
        if c1 or c2:
            return None
        else:
            return q

    def _get_tags(self):
        return (
            self.tags is None
            or self.tags
            or self.keep is not None
            or self.exclude is not None
            or self.must_tags is not None
            or self.geometry
        )

    def as_dict(self):
        """Convert to a dictionary, add keep_keys and exclude_keys as list of tags for filter"""
        attrs = list(self.__dict__.keys())
        return {self._unsubscript(a): getattr(self, a) for a in attrs}

    @staticmethod
    def _map_list(tags, strings):
        if tags is None:
            return None
        else:
            return set([strings[k] for k in tags if k in strings])

    @staticmethod
    def _map_filter(tags, tagmap):
        """Return a set of tuples of tag/value integers for a filter"""

        if tags is None:
            return None, None

        # parse filter all
        res_all = {tagmap[k] for k, v in tags.items() if not v and k in tagmap}

        # parse filter any
        res_any = {
            tagmap[k]: np.array([tagmap[tag] for tag in v if tag in tagmap], dtype=int)
            for k, v in tags.items()
            if k in tagmap
        }

        # convert to tuples if any value in tagmap and unpack lists
        res_any = [
            pack_tagval([k] * len(v), v) for k, v in res_any.items() if len(v) > 0
        ]

        res_any = {item for sublist in res_any for item in sublist}

        if not res_any and len(res_all):
            return None, None

        return res_any, res_all

    @staticmethod
    def _map_area(tags, tagmap):
        res = []
        for k, v in tags.items():
            res.extend(
                [
                    (tagmap[p0] << 32) | tagmap[p1]
                    for p0, p1 in zip([k] * len(v), v)
                    if p0 in tagmap and p1 in tagmap
                ]
            )
        return set(res)

    @staticmethod
    def _unsubscript(val):
        if val[0] == "_":
            return val[1:]
        return val


def pack_tagval(tag, val):
    return [t << 32 | v for t, v in zip(tag, val)]