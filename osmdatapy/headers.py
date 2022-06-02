# Header PBF parsers
import zlib
import array
import numpy as np

from . import protobuf


def parse_header(data):
    """Parse an OSM header, return the Blob datasize"""

    length = len(data)
    offset = 0
    datasize = 0

    while offset < length:

        key, offset, l = protobuf.pbf_key(data, offset)
        if key == 1:
            string = bytearray(data[offset : offset + l]).decode()
            offset += l
        elif key == 2:
            b = bytearray(data[offset : offset + l])
            offset += l
        elif key == 3:
            datasize, offset = protobuf.scalar(data, offset, "int32")
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
        key, offset, l = protobuf.pbf_key(data, offset)

        if key == 1:
            st_offset = offset
            end_offset = offset + l
            res = data[offset : offset + l]
            offset += l
        elif key == 2:
            datasize, offset = protobuf.scalar(data, offset, "int32")
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
        key, offset, l = protobuf.pbf_key(d, offset)

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

    # store results by osm_type
    nodes, dense, ways, relations = [], [], [], []
    ids, lons, lats = array.array("q", []), array.array("q", []), array.array("q", [])

    while offset < block_length:
        key, offset, l = protobuf.pbf_key(block, offset)

        if key == 1:
            strtable, offset = stringtable(block, offset, l)
        elif key == 2:
            offset, osm_id, offset_list, ids, lons, lats = parse_primitive_group(block, offset, l)
            if osm_id==1:
                nodes.extend(offset_list)
                ids.extend(ids)
                lons.extend(lons)
                lats.extend(lats)
            elif osm_id==2:
                dense.append(offset_list)
                ids.extend(ids)
                lons.extend(lons)
                lats.extend(lats)
            elif osm_id==3:
                ways.extend(offset_list)
            else:
                relations.extend(offset_list)

        elif key == 17:
            granularity, offset = protobuf.scalar(block, offset, "int32")
        elif key == 18:
            date_granularity, offset = protobuf.scalar(block, offset, "int32")
        elif key == 19:
            lat_offset, offset = protobuf.scalar(block, offset, "int64")
        elif key == 20:
            lon_offset, offset = protobuf.scalar(block, offset, "int64")
        else:
            offset += l

    metadata = {
        "stringtable": strtable,
        "date_granularity": date_granularity,
        "dense_offsets": dense,
        "node_offsets": nodes,
        "way_offsets": ways,
        "rel_offsets": relations,
    }

    lons = _map_coord(lons, granularity, lon_offset)
    lats = _map_coord(lats, granularity, lat_offset)
    pts = np.array([ids, lons, lats]).T

    return pts, metadata


def _map_coord(coord, gran, offset):
    res = np.asarray(coord)
    return res * gran + offset


def stringtable(block, offset, length):

    stringtable, offset = protobuf.bytelist(block, offset, length)
    stringtable = [bytearray(x) for x in stringtable]
    stringtable = [x.decode("UTF8") for x in stringtable]

    # test if string map only contains simple text
    strset = set(stringtable)
    strset.difference_update(set(["", "source", "source:date"]))

    if len(strset) <= 1:
        stringtable = []

    return stringtable, offset


def parse_primitive_group(block, offset, length):
    """
    Parse a primitive group in data for cache

    Parameter:
    -----------------
    block : block data
    offset : start offset of primitive group
    length : length from offset of primitive group
    
    Return:
    -----------------
    osm_type : primitive type : 1 for node, 2 for dense nodes, 3 for ways, 4 for relations
    offsets : 
        if dense nodes : (offset, length)
        else : list of (id, offset, length)
    geometry :
        if dense nodes or nodes : array of ids, array of longitudes, array of latitudes
        else None, None, None
    """

    group_offset = offset + length
    results = []
    ids = array.array("q", [])
    lons = array.array("q", [])
    lats = array.array("q", [])

    while offset < group_offset:
        key, offset, l = protobuf.pbf_key(block, offset)
        ref_offset = offset

        if key == 1:
            offset, elemid, lon, lat = cached_node(block, offset, l)
            results.append((elemid, ref_offset, l))
            ids.append(elemid)
            lons.append(lon)
            lats.append(lat)
        elif key == 2:
            offset, elemid, lon, lat = cached_dense(block, offset, l)
            results.append((ref_offset, l))
            ids.extend(elemid)
            lons.extend(lon)
            lats.extend(lat)
        elif key == 3 or key == 4:
            offset, elemid = cached_relation_or_way(block, offset, l)
            results.append((elemid, ref_offset, l))
        else:
            offset += l

    if key==2:
        results = results[0]
    
    return offset, key, results, ids, lons, lats


def cached_dense(block, offset, length):
    """ parse dense for cache, return new offset, list of osm ids and coordinates"""

    message_offset = offset + length
    elemid, lon, lat = [0],[0],[0]

    while offset < message_offset:
        key, offset, l = protobuf.pbf_key(block, offset)
        if key == 1:
            elemid, offset = protobuf.large_packed(block, offset, l, "sint64", delta=True)
        elif key == 8:
            lat, offset = protobuf.large_packed(block, offset, l, "sint64", delta=True)
        elif key == 9:
            lon, offset = protobuf.large_packed(block, offset, l, "sint64", delta=True)
        else:
            offset += l

    return message_offset, elemid, lon, lat


def cached_node(block, offset, length, res):
    """ parse a node for cache, return osm id longitude, latitude"""

    message_offset = offset + length

    while offset < message_offset:
        key, offset, l = protobuf.pbf_key(block, offset)
        if key == 1:
            elemid, offset = protobuf.scalar(block, offset, "sint64")
        elif key == 8:
            lat, offset = protobuf.scalar(block, offset, "sint64")
        elif key == 9:
            lon, offset = protobuf.scalar(block, offset, "sint64")
        else:
            offset += l
            elemid, lon, lat = 0,0,0

    return message_offset, elemid, lon, lat


def cached_relation_or_way(block, offset, length):
    """ parse a way or a relation for cache, return new offset and osm id"""

    message_offset = offset + length
    elemid=0
    while offset < message_offset:
        key, offset, l = protobuf.pbf_key(block, offset)
        if key == 1:
            elemid, offset = protobuf.scalar(block, offset, "int64")
            return message_offset, elemid
        else:
            offset += l
    return message_offset, elemid