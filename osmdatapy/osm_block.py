import zlib
import array
import numpy as np

from osmdatapy.simple_primitives import node, way, relation
from osmdatapy.dense_primitives import dense


def parse_block(data, strmap, query, compression="zlib"):
    """
    Parse an OSM pbf Block based on query arguments into ids, tags and rels numpy arrays or None

    Parameters :
    ----------
    data : a data buffer
    stringmap : map from local to global string integer, cached in OSM object
    query : a query dictionnary made from query object for this block
    compression : None or compression type string, "zlib" is the only format supported
    """

    if compression == "zlib":
        bl = zlib.decompress(data)
    else:
        raise NotImplementedError("Compression {0} not implemented".format(compression))

    res = []

    i = query["node_offsets"]
    pack_nodes(res, [node(bl[p : p + l], l, query) for eid, p, l in i], strmap)
    i = query["way_offsets"]
    pack_ways(res, [way(bl[p : p + l], l, query) for eid, p, l in i], strmap)
    i = query["rel_offsets"]
    pack_rels(res, [relation(bl[p : p + l], l, query) for eid, p, l in i], strmap)
    pack_dense(res, dense, query, bl, strmap)

    return res


def pack_nodes(res, nodes, strmap):
    """Merge list of nodes in a result tuple"""

    if nodes is None or not nodes:
        return None
    ids, meta, tags, vals = zip(*[x for x in nodes if x])
    l= len(ids)

    ids = pack_ids(0, ids, meta)
    relids = np.repeat(range(l), 0)
    z = np.zeros(l, dtype="int")
    relres = np.array([relids, z, z, z, z])

    res.append((ids, pack_tags(tags, vals, strmap, l), relres))


def pack_ways(res, ways, strmap):
    """Merge list of ways in a result tuple"""

    if ways is None or not ways:
        return None
    ids, meta, tags, vals, mems, geoms = zip(*[x for x in ways if x])
    l = len(ids)

    ids = pack_ids(1, ids, meta)
    relids = _local_ids(l, mems)

    z = np.zeros(len(relids), dtype="int")
    g = np.repeat(geoms, [len(x) for x in mems])
    relres = np.array([relids, np.hstack(mems), z, z, g]).T

    res.append((ids, pack_tags(tags, vals, strmap, l), relres))


def pack_rels(res, rels, strmap):
    """Merge list of ways in a result tuple"""

    if rels is None or not rels:
        return None
    ids, meta, tags, vals, mems, types, roles, geoms = zip(*[x for x in rels if x])
    l = len(ids)

    ids = pack_ids(2, ids, meta)
    roles = strmap[np.hstack(roles)]
    relids = _local_ids(l, mems)
    g = np.repeat(geoms, [len(x) for x in mems])
    relres = np.array([relids, np.hstack(mems), np.hstack(types), roles, g]).T

    res.append((ids, pack_tags(tags, vals, strmap, l), relres))


def pack_dense(res, dense, query, block, strmap):
    if query["dense_offsets"] is None:
        return None

    offset, l = query["dense_offsets"]
    ids, tags, rels = dense(query, block[offset : offset + l], l)

    tags[:, 1] = strmap[tags[:, 1]]
    tags[:, 2] = strmap[tags[:, 2]]

    res.append((ids, tags, rels))


def _local_ids(id_length, array):
    return np.repeat(range(id_length), np.array([len(x) for x in array]))


def pack_tags(tags, vals, strmap, l):
    if tags is None:
        return None

    t = [x for x in tags if x is not None]
    if not t:
        return None
    v = [x for x in vals if x is not None]
    tagids = _local_ids(l, t)
    return np.column_stack([tagids, strmap[np.hstack(t)], strmap[np.hstack(v)]])


def pack_ids(osmtype, ids, meta):
    l = len(ids)
    types = np.repeat(osmtype, l)
    meta = v = [x for x in meta if x]
    if not meta:
        return np.column_stack([ids, types])
    return np.column_stack([ids, types, np.hstack(list(meta)).reshape((l, 3))])