# Dense Nodes and Info Primitives PBF parsers

import numpy as np
from array import array

from osmdatapy.protobuf import large_packed, get_key, keyvals


def dense(query, block, length):

    empty_res = np.array([], int), np.array([], int), np.array([], int)
    if not query["nodes"]:
        return empty_res

    elemid, version, time, change = None, -1, 0, 0
    tagids, tags, vals = None, None, None
    offset = 0

    while offset < length:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = large_packed(block, offset, l, "sint64", delta=True)
        elif key == 5:
            info, offset = dense_info(block, offset, l, query)
        elif key == 10:
            tagids, tags, vals, offset = keyvals(block, offset, l)
        else:
            offset += l

    if elemid is None or len(elemid) == 0:
        return empty_res

    elemid, tagids, tags, vals = filter_by_query(query, elemid, tagids, tags, vals)

    # add results to arrays
    l = len(elemid)

    ids = np.column_stack(
        [
            elemid,
            np.repeat(0, l),
            _array_def(version, l),
            _array_def(time, l),
            _array_def(change, l),
        ]
    )
    tags = np.column_stack([tagids, tags, vals])
    tags = _filter_dense_tags(tags, query["tags"])

    return ids, tags, None


def dense_info(block, offset, length, query):

    version, time, change = -1, 0, 0

    message_offset = offset + length
    if query is None or not query["metadata"]:
        return message_offset, version, time, change

    while offset < message_offset:
        key, offset, l = get_key(block, offset)

        if key == 1:
            version, offset = large_packed(block, offset, l, "int32")
        elif key == 2:
            timestamp, offset = large_packed(block, offset, l, "sint64", True)
        elif key == 3:
            changeset, offset = large_packed(block, offset, l, "sint64", True)
        else:
            offset += length

    return message_offset, version, time, change


def _array_def(value, len_elem):
    if isinstance(value, int):
        return np.repeat(value, len_elem)
    else:
        return value


def filter_by_query(query, ids, tagids, tags, vals):
    """Returns subset of ids, tagids, tags and vals matching query"""

    if len(ids) == 0 or query is None:
        return ids, tagids, tags, vals

    # convert to numpy arrays
    idarr = np.asarray(ids, "int")
    tagidarr = np.asarray(tagids, "int")
    tagarr = np.asarray(tags, "int")
    valarr = np.asarray(vals, "int")

    # set of osm ids to keep
    maskid = np.full(len(ids), False)

    # filter on tags
    if not tags:
        tag_mask = filter_by_tags(query, tagarr, valarr)
        tagid_mask = np.in1d(
            idarr, idarr[np.unique(tagidarr[tag_mask])], assume_unique=True
        )
    else:
        tagid_mask = np.full(len(ids), False)

    # filter on osm ids
    if query["node_set"] is not None:
        nodesetarr = np.fromiter(query["node_set"], "int")
        nodeset_mask = np.in1d(idarr, nodesetarr, assume_unique=True)
    else:
        nodeset_mask = np.full(len(ids), False)

    maskid = maskid | tagid_mask | nodeset_mask

    idarr = idarr[maskid]
    idpos = np.arange(len(ids))[maskid]

    # reindex tagids
    tag_mask = np.in1d(tagidarr, idpos)
    tagidarr = tagidarr[tag_mask]
    tagarr = tagarr[tag_mask]
    valarr = valarr[tag_mask]

    # change tagidarr to positions in idarr
    idsorted = np.argsort(idpos)
    pos = np.searchsorted(idpos[idsorted], tagidarr)
    tagidarr = idsorted[pos]

    return (
        array.array("q", idarr),
        array.array("q", tagidarr),
        array.array("q", tagarr),
        array.array("q", valarr),
    )


def filter_by_tags(query, tags, vals):
    """returns a boolean mask on tags"""

    mask = np.full(tags.shape, True)

    if query["must_tags"] is not None:
        mask = np.in1d(tags, np.fromiter(query["must_tags"], dtype="int"))

    if query["no_tags"]:
        return mask

    # list of keep unique ids
    kps = _filter_pairs(query["keep"], tags, vals)
    kps = kps | _filter_all(query["keep_all"], tags)
    exs = _filter_pairs(query["excl"], tags, vals)
    exs = exs | _filter_all(query["excl_all"], tags)

    if query["keep_first"]:
        return mask & (kps & np.logical_not(exs))
    else:
        return mask & (np.logical_not(exs) | kps)


def _filter_pairs(query, tags, vals):
    if query is None:
        return np.full(tags.shape, False)
    kp_array = np.fromiter(query, dtype="int")
    kp_packed = np.bitwise_or(np.left_shift(tags, 32), vals)
    return np.in1d(kp_packed, kp_array)


def _filter_all(query, tags):
    if query is None:
        return np.full(tags.shape, False)
    return np.in1d(tags, np.fromiter(query, dtype="int"))


def _filter_dense_tags(tags, qtags):

    if qtags is None or qtags.shape[0] == 0 or tags.shape[0] == 0:
        return tags

    return tags[np.in1d(tags[:, 1], qtags, assume_unique=True)]