# Header PBF parsers

from .protobuf import scalar, packed, get_key, keyvals, bytelist


def parse_header(data):
    """Parse an OSM header, return the Blob datasize"""

    length = len(data)
    offset = 0
    datasize = 0

    while offset < length:

        key, offset, l = get_key(data, offset)
        if key == 1:
            string = bytearray(data[offset : offset + l]).decode()
            offset += l
        elif key == 2:
            b = bytearray(data[offset : offset + l])
            offset += l
        elif key == 3:
            datasize, offset = scalar(data, offset, "int32")
        else:
            offset += l

    return (datasize, string)


def parse_blob(data):
    """Parse an OSM blob, returns the start and end offset, compression type or None, and data"""

    length = len(data)
    offset = 0
    datasize = 0
    compression = None

    while offset < length:
        key, offset, l = get_key(data, offset)

        if key == 1:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
        elif key == 2:
            datasize, offset = scalar(data, offset, "int32")
        elif key == 3:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
            compression = "zlib"
        elif key == 4:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
            compression = "lzma"
        elif key == 6:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
            compression = "lz4"
        elif key == 7:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
            compression = "ztsd"
        else:
            offset += l

    return st_offset, end_offset, compression, res


def parse_blockheader(data, compression):
    """Valide block header content based on parsing capabilities"""

    if compression is not None and compression != "zlib":
        raise NotImplementedError("Compression {0} not implemented".format(compression))

    offset = 0
    features = []
    opt_features = []

    if compression == "zlib":
        block_data = bytearray(zlib.decompress(data))
        length = len(block_data)
        d = memoryview(block_data)
    else:
        block_data = bytearray(data)
        d = memoryview(block_data)
        length = len(block_data)

    while offset < length:
        key, offset, l = get_key(d, offset)

        # required features
        if key == 4:
            val = bytearray(d[offset : offset + l]).decode()
            offset += l
            features.append(val)

        # optional features
        elif key == 5:
            val = bytearray(d[offset : offset + l]).decode()
            offset += l
            opt_features.append(val)
        else:
            offset += l

    for feat in features:
        if not (feat in ["OsmSchema-V0.6", "DenseNodes"]):
            raise NotImplementedError("Feature {0} not implemented".format(feat))

    return features, opt_features


def parse_cache_block(data, compression="zlib"):
    """
    Parse an OSM pbf Block into a pts geometry numpy array and metadata dictionary

    Parameters :
    ----------
    data : a data buffer
    compression : None or compression type string, "zlib" is the only format supported
    """

    if compression == "zlib":
        block_data = zlib.decompress(data)
        block = memoryview(block_data)
    elif compression is None:
        block = memoryview(block_data)
    else:
        raise NotImplementedError("Compression {0} not implemented".format(compression))

    offset = 0
    block_length = len(block)

    # default block metadata
    granularity = 100
    date_granularity = 100
    lat_offset = 0
    lon_offset = 0

    res = {
        "i_id": array.array("q", []),
        "i_lon": array.array("q", []),
        "i_lat": array.array("q", []),
    }

    while offset < block_length:
        key, offset, l = get_key(block, offset)

        if key == 1:
            strtable, offset = stringtable(block, offset, l)
        elif key == 2:
            (
                offset,
                dense_pos,
                node_pos,
                way_pos,
                rel_pos,
            ) = cached_primitives(block, offset, l, res)
        elif key == 17:
            granularity, offset = scalar(block, offset, "int32")
        elif key == 18:
            date_granularity, offset = scalar(block, offset, "int32")
        elif key == 19:
            lat_offset, offset = scalar(block, offset, "int64")
        elif key == 20:
            lon_offset, offset = scalar(block, offset, "int64")
        else:
            offset += length

    metadata = {
        "stringtable": strtable,
        "date_granularity": date_granularity,
        "dense_offsets": dense_pos,
        "node_offsets": node_pos,
        "way_offsets": way_pos,
        "rel_offsets": rel_pos,
    }

    lon = _map_coord(res["i_lon"], granularity, lon_offset)
    lat = _map_coord(res["i_lat"], granularity, lat_offset)
    pts = np.array([np.asarray(res["i_id"]), lon, lat]).T

    return pts, metadata


def _map_coord(coord, gran, offset):
    res = np.asarray(coord)
    return res * gran + offset


def stringtable(block, offset, length):

    stringtable, offset = bytelist(block, offset, length)
    stringtable = [bytearray(x) for x in stringtable]
    stringtable = [x.decode("UTF8") for x in stringtable]

    # test if string map only contains simple text
    strset = set(stringtable)
    strset.difference_update(set(["", "source", "source:date"]))

    if len(strset) <= 1:
        stringtable = None

    return stringtable, offset


def cached_primitives(block, offset, length, res):

    group_offset = offset + length
    elemid, dense_pos = None, None
    node_pos = []
    way_pos = []
    rel_pos = []

    while offset < group_offset:
        key, offset, l = get_key(block, offset)
        ref_offset = offset

        if key == 1:
            elemid, offset = cached_node(block, offset, l, res)
            node_pos.append((elemid, ref_offset, l))
        elif key == 2:
            dense_pos = (offset, l)
            pos = cached_dense(block, offset, l, res)
        elif key == 3:
            elemid, offset = cached_relway(block, offset, l)
            way_pos.append((elemid, ref_offset, l))
        elif key == 4:
            elemid, offset = cached_relway(block, offset, l)
            rel_pos.append((elemid, ref_offset, l))
        # pass if key is changeset or key not parsed depending on query
        else:
            offset += l

    return offset, dense_pos, node_pos, way_pos, rel_pos


def cached_dense(block, offset, length, res):

    message_offset = offset + length

    while offset < message_offset:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = large_packed(block, offset, l, "sint64", delta=True)
        elif key == 8:
            lat, offset = large_packed(block, offset, l, "sint64", delta=True)
        elif key == 9:
            lon, offset = large_packed(block, offset, l, "sint64", delta=True)
        else:
            offset += l

    res["i_id"].extend(elemid)
    res["i_lon"].extend(lon)
    res["i_lat"].extend(lat)

    return message_offset


def cached_node(block, offset, length, res):

    message_offset = offset + length

    while offset < message_offset:
        key, offset, l = get_key(block, offset)

        if key == 1:
            elemid, offset = scalar(block, offset, "sint64")
        elif key == 8:
            lat, offset = scalar(block, offset, "sint64")
        elif key == 9:
            lon, offset = scalar(block, offset, "sint64")
        else:
            offset += l
    res["i_id"].append(elemid)
    res["i_lon"].append(lon)
    res["i_lat"].append(lat)

    return elemid, message_offset


def cached_relway(block, offset, length):

    message_offset = offset + length
    while offset < message_offset:
        key, offset, l = get_key(block, offset)
        if key == 1:
            elemid, offset = scalar(block, offset, "int64")
            return elemid, message_offset
        else:
            offset += l
    return None