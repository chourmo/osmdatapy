#cython: language_level=3
# Protocol buffer parsing functions

from libc.stdint cimport *
from cpython cimport array
import array
cimport cython

@cython.boundscheck(False)
def packed(const unsigned char[:] block not None, Py_ssize_t offset, Py_ssize_t length, str scalar_type, bint delta=False):
    """
    returns a python array of repeated scalar read with func and new offset
    data type is coerced to long long signed 64int, in a 'q' python array
    if delta is True, apply delta decoding
    """
    
    # maximum size of array is length if all data fits in one byte
    cdef array.array res_template = array.array('q', [])
    cdef array.array res
    res = array.clone(res_template, length, zero=True)
    
    if scalar_type=="int32" or scalar_type=="enum" or scalar_type=="bool":
        offset, size = packed_int32(block, offset, length, delta, res)
    
    elif scalar_type=="uint32":
        offset, size = packed_uint32(block, offset, length, res)
    
    elif scalar_type=="int64":
        offset, size = packed_int64(block, offset, length, delta, res)
        
    elif scalar_type == "sint32":
        offset, size = packed_signedint32(block, offset, length, delta, res)
    
    elif scalar_type == "sint64":
        offset, size = packed_signedint64(block, offset, length, delta, res)
    else:
        size =0
    
    return res[:size], offset


def large_packed(const unsigned char[:] block not None, Py_ssize_t offset, Py_ssize_t length, str scalar_type, bint delta=False):
    """
    returns a python array of repeated scalar read with func and new offset
    data type is coerced to long long signed 64int, in a 'q' python array
    if delta is True, apply delta decoding
    """
    
    # maximum size of array is length if all data fits in one byte
    cdef array.array res_template = array.array('q', [])
    cdef array.array res = array.clone(res_template, length, zero=True)
    cdef int64_t[:] resview = res
    
    if scalar_type=="int32" or scalar_type=="enum" or scalar_type=="bool":
        offset, size = packed_int32(block, offset, length, delta, resview)
    
    elif scalar_type=="uint32":
        offset, size = packed_uint32(block, offset, length, resview)
    
    elif scalar_type=="int64":
        offset, size = packed_int64(block, offset, length, delta, resview)
        
    elif scalar_type == "sint32":
        offset, size = packed_signedint32(block, offset, length, delta, resview)
    
    elif scalar_type == "sint64":
        offset, size = packed_signedint64(block, offset, length, delta, resview)
    else:
        size =0
        
    return res[:size], offset
        

def keyvals(const unsigned char[:] block not None, Py_ssize_t offset, Py_ssize_t length):
    """
    extract dense nodes keyvals in a 3 integer numpy arrays : positon in elemid, key and value
    """
    
    cdef array.array id_template = array.array('q',[])
    cdef array.array ids, keys, vals
    cdef bint key = True
    cdef Py_ssize_t cnter = 0
    cdef Py_ssize_t idpos = 0
    cdef int value    
    
    ids = array.clone(id_template, length, zero=True)
    keys = array.clone(id_template, length, zero=True)
    vals = array.clone(id_template, length, zero=True)
    
    rep_offset = offset + length
    
    while offset < rep_offset:
        value, offset = _varint32(block, offset)
        if value==0:
            idpos += 1
            key=True
        elif key:
            keys[cnter] = value
            ids[cnter] = idpos
            cnter+=1
            key = False
        else:
            vals[cnter] = value
            key=True

    return ids[:cnter], keys[:cnter], vals[:cnter], offset


def bytelist(const unsigned char[:] block not None, Py_ssize_t offset, Py_ssize_t length):
    """ Returns a byte list"""
    cdef list res = []
    cdef int key
    cdef Py_ssize_t bytesize
    cdef Py_ssize_t list_offset = offset + length
    
    while offset < list_offset:
        key, offset, bytesize = _pbf_key(block, offset)
        res.append(block[offset:offset+bytesize])
        offset = offset + bytesize
                
    return res, offset

def pbf_key(const unsigned char[:] block not None, Py_ssize_t offset):
    """
    returns key, updated offset and the length of the value
        - for varints, length is 0
        - for length delimited values, parse length and shift offset to the start of values
    """    
    return  _pbf_key(block, offset)


def scalar(const unsigned char[:] block not None, Py_ssize_t offset, str scalar_type):
    """ Returns a scalar and new offset """
    
    cdef Py_ssize_t bytesize, new_offset
    cdef int key, val
    
    if scalar_type == 'bool' or scalar_type == "int32" or scalar_type == "enum":
        val, new_offset = _varint32(block, offset)
    
    elif scalar_type =="uint32":
        val, new_offset = _varuint32(block, offset)
    
    elif scalar_type== "int64":
        val, new_offset = _varint64(block, offset)
    
    elif scalar_type == "sint32":
        val, new_offset = _signedvarint32(block, offset)

    elif scalar_type == "sint64":
        val, new_offset = _signedvarint64(block, offset)          

    else:
        val = 0
        
    return val, new_offset

def pack_tag_val(int64_t[:] tags, int64_t[:] vals):
    
    cdef list res = []
    cdef size_t l = len(tags)
    
    if l != len(vals):
        raise ValueError("tags and vals must hase same length")
    
    for i in range(l):
        res.append(tags[i] << 32 | vals[i])
        
    return res


#-------------------------------------------------------------------------------
# Arrays

@cython.boundscheck(False)
@cython.wraparound(False)
cdef (int, int) packed_int32(const unsigned char[:] block, int offset, int length, bint delta, int64_t[:] arr):
    """
    Deserialize a packed list of signed int32, optionally applying delta decoding
    Add to results array arr as 64-bit long long
    """
    
    cdef int rep_offset = offset + length
    cdef int size = 0
    cdef int64_t delta_val, value
    delta_val= 0
        
    while offset < rep_offset:
        value, offset = _varint32(block, offset)
        if delta:
            value = delta_val + value
            delta_val = value
        arr[size] = value
        size+=1
    
    return offset, size

@cython.boundscheck(False)
@cython.wraparound(False)
cdef (int, int) packed_uint32(const unsigned char[:] block, int offset, int length, int64_t[:] arr):
    """
    Deserialize a packed list of signed int32, cannot be deltacoded
    Add to results array arr as 64-bit long long
    """
    
    cdef int rep_offset = offset + length
    cdef int size = 0
    cdef int64_t value    
    
    while offset < rep_offset:
        value, offset = _varuint32(block, offset)
        arr[size] = value
        size+=1
    
    return offset, size

@cython.boundscheck(False)
@cython.wraparound(False)
cdef (int, int) packed_int64(const unsigned char[:] block, int offset, int length, bint delta, int64_t[:] arr):
    """
    Deserialize a packed list of signed int64, optionally applying delta decoding
    Add to results array arr as 64-bit long long
    """
    
    cdef int rep_offset = offset + length
    cdef int size = 0
    cdef int64_t delta_val, value
    
    delta_val = 0
    
    while offset < rep_offset:
        value, offset = _varint64(block, offset)
        if delta:
            value = delta_val + value
            delta_val = value
        arr[size] = value
        size+=1
    
    return offset, size

@cython.boundscheck(False)
@cython.wraparound(False)
cdef (int, int) packed_signedint32(const unsigned char[:] block, int offset, int length, bint delta, int64_t[:] arr):
    """
    Deserialize a packed list of signed int32 with zig-zag coding, optionally applying delta decoding
    Add to results array arr as 64-bit long long
    """
    
    cdef int rep_offset = offset + length
    cdef int size = 0
    cdef int64_t delta_val, value
    
    delta_val = 0
    
    while offset < rep_offset:
        value, offset = _signedvarint32(block, offset)
        if delta:
            value = delta_val + value
            delta_val = value
        arr[size] = value
        size+=1
    
    return offset, size

@cython.boundscheck(False)
@cython.wraparound(False)
cdef (int, int) packed_signedint64(const unsigned char[:] block, Py_ssize_t offset, Py_ssize_t length, bint delta, int64_t[:] arr):
    """
    Deserialize a packed list of signed int64 with zig-zag coding, optionally applying delta decoding
    Add to results array arr as 64-bit long long
    """
    
    cdef Py_ssize_t rep_offset = offset + length
    cdef Py_ssize_t size = 0
    cdef int64_t delta_val, value
    
    delta_val = 0
    
    while offset < rep_offset:
        value, offset = _signedvarint64(block, offset)
        if delta:
            value = delta_val + value
            delta_val = value
        arr[size] = value
        size+=1

    return offset, size


#-------------------------------------------------------------------------------
# Scalars

@cython.boundscheck(False)
cdef (int, int, int64_t) _pbf_key(const unsigned char[:] block, Py_ssize_t offset):
    
    cdef int64_t v, length
    cdef Py_ssize_t new_offset, key, wiretype
        
    v, new_offset = _varint64(block, offset)
    
    # split key and wiretype in last 3 bits
    key = v >> 3
    wiretype = v & 0x7
    
    if wiretype == 1:
        length = 8
    elif wiretype == 5:
        length = 4

    # if length delimited, read value length and shift offset
    elif wiretype == 2:
        length, new_offset = _varint64(block, new_offset)
        return key, new_offset, length 
    else:
        length = 0
    
    return key, new_offset, length

@cython.boundscheck(False)
cdef (int64_t, int) _varint32(const unsigned char[:] block, Py_ssize_t offset):
    """
    Deserialize a protobuf varint starting from offset in memory
    update offset based on number of bytes consumed
    """
    
    cdef int32_t base = 1
    cdef Py_ssize_t index = 0
    cdef char val_byte = block[offset]
    cdef int32_t value = (val_byte & 0x7F)

    while (val_byte & 0x80):
        base *= 128
        index += 1
        val_byte = block[offset + index]
        value += (val_byte & 0x7F) * base
 
    offset += (index + 1)
    return <int64_t>value, offset

@cython.boundscheck(False)
cdef (int64_t, int) _varuint32(const unsigned char[:] block, Py_ssize_t offset):
    """
    Deserialize a protobuf varint starting from offset in memory
    update offset based on number of bytes consumed.
    """
    
    cdef uint32_t base = 1
    cdef Py_ssize_t index = 0
    cdef char val_byte = block[offset]
    cdef uint32_t value = (val_byte & 0x7F)

    while (val_byte & 0x80):
        base *= 128
        index += 1
        val_byte = block[offset + index]
        value += (val_byte & 0x7F) * base
 
    offset += (index + 1)
    return <int64_t>value, offset

@cython.boundscheck(False)
cdef (int64_t, int) _varint64(const unsigned char[:] block, Py_ssize_t offset):
    """
    Deserialize a protobuf varint starting from offset in memory
    update offset based on number of bytes consumed.
    """
    cdef int64_t base = 1
    cdef Py_ssize_t index = 0
    cdef char val_byte = block[offset]
    cdef int64_t value = (val_byte & 0x7F)
    
    while (val_byte & 0x80):
        base *= 128
        index += 1
        val_byte = block[offset + index]
        value += (val_byte & 0x7F) * base

    offset += (index + 1)
    return <int64_t>value, offset

@cython.boundscheck(False)
cdef (int64_t, int) _signedvarint32(const unsigned char[:] block, Py_ssize_t offset):
    """
    Deserialize a signed protobuf varint starting from offset in memory;
    update offset based on number of bytes consumed.
    """
    cdef int32_t base = 1
    cdef Py_ssize_t index = 0
    cdef char val_byte = block[offset]
    cdef uint32_t value = (val_byte & 0x7F)
    
    while (val_byte & 0x80):
        base *= 128
        index += 1
        val_byte = block[offset + index]
        value += (val_byte & 0x7F) * base

    offset += (index + 1)
    
    #zigzag decode
    return <int64_t>((value >> 1) ^ (-(value & 1))), offset

@cython.boundscheck(False)
cdef (int64_t, int) _signedvarint64(const unsigned char[:] block, Py_ssize_t offset):
    """
    Deserialize a signed protobuf varint starting from offset in memory;
    update offset based on number of bytes consumed.
    """
    cdef int64_t base = 1
    cdef Py_ssize_t index = 0
    cdef char val_byte = block[offset]
    cdef uint64_t value = (val_byte & 0x7F)

    while (val_byte & 0x80):
        base *= 128
        index += 1
        val_byte = block[offset + index]
        value += (val_byte & 0x7F) * base

    offset += (index + 1)
    
    #zigzag decode
    return <int64_t>((value >> 1) ^ (-(value & 1))), offset