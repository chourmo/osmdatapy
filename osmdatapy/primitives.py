# Scalar Primitives PBF parsers

import numpy as np
from array import array

from osmdatapy.protobuf import scalar, packed, get_key, pack_tag_val


def node(block, length, query):

    if query["metadata"]:
        version, time, change = -1, 0, 0

    meta, tags, tag_set, vals = None, None, None, None
    offset = 0

    while offset < length:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = scalar(block, offset, "int64")

        elif key == 2 and query["get_tags"]:
            tags, offset = packed(block, offset, l, "uint32")
            tag_set = set(tags)
            if not _validate_tag(tag_set, query["must_tags"]):
                return None

        elif key == 3 and query["get_tags"]:
            vals, offset = packed(block, offset, l, "uint32")
        elif key == 4 and query["metadata"]:
            offset, version, time, change = info(block, offset, l, query)
        else:
            offset += l

    if not _validate_tagval(query, tag_set, tags, vals):
        return None

    if query["metadata"]:
        meta = [version, time, change]

    tags, vals = _filter_tags(tags, vals, query["tags"])

    return elemid, meta, tags, vals


def way(block, length, query):

    if query["metadata"]:
        version, time, change = -1, 0, 0

    meta, tags, tag_set, vals, mems = None, None, None, None, None
    offset = 0

    while offset < length:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = scalar(block, offset, "int64")

        elif key == 2 and query["get_tags"]:
            tags, offset = packed(block, offset, l, "uint32")
            tag_set = set(tags)
            if not _validate_tag(tag_set, query["must_tags"]):
                return None

        elif key == 3 and query["get_tags"]:
            vals, offset = packed(block, offset, l, "uint32")

        elif key == 4 and query["metadata"]:
            offset, version, time, change = info(block, offset, l, query)

        elif key == 8:
            mems, offset = packed(block, offset, l, "sint64", True)

            # ways must have at least 2 points
            if len(mems) < 2:
                return None
        else:
            offset += l

    if not _validate_tagval(query, tag_set, tags, vals):
        return None

    if query["metadata"]:
        meta = [version, time, change]
    tags, vals = _filter_tags(tags, vals, query["tags"])
    geom = _way_geotype(query, tags, tag_set, vals, mems)

    return elemid, meta, tags, vals, np.asarray(mems), geom


def relation(block, length, query):

    if query["metadata"]:
        version, time, change = -1, 0, 0

    meta, tags, tag_set, vals = None, None, None, None
    roles, mems, types = None, None, None
    offset = 0

    while offset < length:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = scalar(block, offset, "int64")

        elif key == 2 and query["get_tags"]:
            tags, offset = packed(block, offset, l, "uint32")
            tag_set = set(tags)
            if not _validate_tag(tag_set, query["must_tags"]):
                return None

        elif key == 3 and query["get_tags"]:
            vals, offset = packed(block, offset, l, "uint32")

        elif key == 4 and query["metadata"]:
            offset, version, time, change = info(block, offset, l, query)

        elif key == 8:
            roles, offset = packed(block, offset, l, "int32")

        elif key == 9:
            mems, offset = packed(block, offset, l, "sint64", delta=True)

        elif key == 10:
            types, offset = packed(block, offset, l, "enum")
            type_set = set(types)
            if not _validate_tag(type_set, query["relation_type"]):
                return None
        else:
            offset += l

    if not _validate_tagval(query, tag_set, tags, vals):
        return None

    geom = _rel_geotype(query, vals, types)

    if query["metadata"]:
        meta = [version, time, change]
    tags, vals = _filter_tags(tags, vals, query["tags"])

    mems = np.asarray(mems)
    types = np.asarray(types)
    roles = np.asarray(roles)

    return elemid, meta, tags, vals, mems, types, roles, geom


def info(block, offset, length, query):

    message_offset = offset + length
    version, time, change = -1, 0, 0

    if query is None:
        return message_offset, version, time, change

    while offset < message_offset:

        key, offset, l = get_key(block, offset)

        if key == 1:
            version, offset = scalar(block, offset, "int32")
        elif key == 2:
            time, offset = scalar(block, offset, "int32")
        elif key == 3:
            change, offset = scalar(block, offset, "int64")
        else:
            offset += l

    return message_offset, version, time, change


# -------------------------------------------------------------
# validation of tags and ids


def _validate_tag(set_values, reference):
    if reference is None:
        return True
    if not set_values:
        return False
    return not set_values.isdisjoint(reference)


def _validate_tagval(query, tagset, tags, values):

    # no tags and must have tags
    if tags is None and query["must_tags"] is not None:
        return False

    # no tags or tags:values in query, or no tags
    if query["no_tagval"] or tags is None or not tags:
        return not query["keep_first"]

    packed = set()
    if query["excl"] is not None or query["keep"] is not None:
        packed = set(pack_tag_val(tags, values))

    kps = False
    if query["keep"] is not None:
        kps |= not query["keep"].isdisjoint(packed)
    if query["keep_all"] is not None:
        kps |= not query["keep_all"].isdisjoint(tagset)

    exs = False
    if query["excl"] is not None:
        exs |= not query["excl"].isdisjoint(packed)
    if query["excl_all"] is not None:
        exs |= not query["excl_all"].isdisjoint(tagset)

    if query["keep_first"]:
        return kps and not exs
    else:
        return not exs or kps


def _filter_tags(tags, vals, qtags):
    if tags is None or len(qtags) == 0:
        return None, None

    if qtags is None:
        return np.asarray(tags), np.asarray(vals)
    mask = [t in qtags for t in tags]
    tags = np.asarray(tags)[mask]
    vals = np.asarray(vals)[mask]
    return tags, vals


# -------------------------------------------------------------
# line or area heuristics


def _is_area(query, tags, tag_set, vals):

    if not query["is_area_key"]:
        return False

    pairs = set(
        [(t << 32) | v for t, v in zip(tags, vals) if t in query["is_area_key"]]
    )

    if not query["area_no"] and not query["area_no"].isdisjoint(pairs):
        return False

    if not query["is_area"] and not query["is_area"].isdisjoint(pairs):
        return True

    if not query["not_area"] and not query["not_area"].isdisjoint(pairs):
        return False

    q = query["is_area_key_any_value"]
    return q and not q.isdisjoint(tag_set)


def _is_closed_way(pts):
    return pts[0] == pts[-1]


def _way_geotype(query, tags, tag_set, vals, refs):
    """Heuristic for area or linestring identification of ways, returns 1 for linestrings, 3 for areas"""

    # default to linestring if no tags
    if tags is None or not query["geometry"] or not query["area"]:
        return 0

    len_refs = len(refs)

    # not a geometry if just one point
    if len_refs == 1:
        return 0

    # linestring if 2 or 3 points
    if len_refs < 4:
        return 2

    # first and last point must be identical
    if not _is_closed_way(refs):
        return 2

    # area based on tags and values
    if _is_area(query, tags, tag_set, vals):
        return 3
    else:
        return 2


def _rel_geotype(query, vals, types):

    if not query["geometry"] or vals is None:
        return 0

    # UNIMPLEMENTED relation with points or relations, no geometry
    if 0 in types or 2 in types:
        return 0

    # dispatch on tag value e.g multipolygon...
    val_set = set(vals)

    if not val_set.isdisjoint(query["rel_line"]):
        return 2
    elif not val_set.isdisjoint(query["rel_area"]):
        return 3

    return 0