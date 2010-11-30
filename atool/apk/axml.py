# -*- coding: utf-8 -*-

'''
A convertor for android compiled binary xml to plain xml.
Format can be found in android source code:
    $ANDROID_ROOT/framework/base/include/util/ResourceType.h
    $ANDROID_ROOT/framework/base/include/util/ResourceTable.h
    ...

some structures:
    Chunk_header (8 bytes):
        uint16_t type
        uint16_t headerSize
        uint32_t size

    StringPool_header (28 bytes):
        Chunk_header header
        uint32_t stringCount
        uint32_t styleCount
        uint32_t flags
        uint32_t stringStart
        uint32_t styleStart

    StringPool_ref (4 bytes):
        uint32_t index

    Tree_node (16 bytes):
        Chunk_header header
        uint32_t lineNumber
        StringPool_ref comment

    Tree_attrExt (20 bytes):
        StringPool_ref ns
        StringPool_ref name
        uint16_t attributeStart
        uint16_t attributeSize
        uint16_t attributeCount
        uint16_t idIndex
        uint16_t classIndex
        uint16_t styleIndex

    Tree_endElementExt (8 bytes)
        StringPool_ref ns
        StringPool_ref name

    Res_value (8 bytes):
        uint16_t size
        uint8_t res0  # always 0
        uint8_t dataType
        uint32_t data

    Tree_attribute (20 bytes):
        StringPool_ref ns
        StringPool_ref name
        StringPool_ref rawValue
        Res_value typedValue

'''

import sys
import os
from struct import unpack

# chunk header size
HEADER_SIZE = 8
# StringPool header size
SP_HEADER_SIZE = 28
# node header size
NODE_HEADER_SIZE = 16

RES_NULL_TYPE = 0x0000
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_TYPE = 0x0002
RES_XML_TYPE = 0x0003

# Chunk types in RES_XML_TYPE
RES_XML_FIRST_CHUNK_TYPE = 0x0100
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_CDATA_TYPE = 0x0104
RES_XML_LAST_CHUNK_TYPE = 0x017f
# This contains a uint32_t array mapping strings in the string
# pool back to resource identifiers.  It is optional.
RES_XML_RESOURCE_MAP_TYPE = 0x0180

# Chunk types in RES_TABLE_TYPE
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202

RES_MAP = {
    RES_NULL_TYPE: 'RES_NULL_TYPE',
    RES_STRING_POOL_TYPE: 'RES_STRING_POOL_TYPE',
    RES_TABLE_TYPE: 'RES_TABLE_TYPE',
    RES_XML_TYPE: 'RES_XML_TYPE',
    RES_XML_FIRST_CHUNK_TYPE: 'RES_XML_FIRST_CHUNK_TYPE',
    RES_XML_START_NAMESPACE_TYPE: 'RES_XML_START_NAMESPACE_TYPE',
    RES_XML_END_NAMESPACE_TYPE: 'RES_XML_END_NAMESPACE_TYPE',
    RES_XML_START_ELEMENT_TYPE: 'RES_XML_START_ELEMENT_TYPE',
    RES_XML_END_ELEMENT_TYPE: 'RES_XML_END_ELEMENT_TYPE',
    RES_XML_CDATA_TYPE: 'RES_XML_CDATA_TYPE',
    RES_XML_LAST_CHUNK_TYPE: 'RES_XML_LAST_CHUNK_TYPE',
    RES_XML_RESOURCE_MAP_TYPE: 'RES_XML_RESOURCE_MAP_TYPE',
    RES_TABLE_PACKAGE_TYPE: 'RES_TABLE_PACKAGE_TYPE',
    RES_TABLE_TYPE_TYPE: 'RES_TABLE_TYPE_TYPE',
    RES_TABLE_TYPE_SPEC_TYPE: 'RES_TABLE_TYPE_SPEC_TYPE'
}

## type of data value
# Contains no data.
TYPE_NULL = 0x00
# The 'data' holds a ResTable_ref, a reference to another resource table entry.
TYPE_REFERENCE = 0x01
# The 'data' holds an attribute resource identifier.
TYPE_ATTRIBUTE = 0x02
# The 'data' holds an index into the containing resource table's
# global value string pool.
TYPE_STRING = 0x03
# The 'data' holds a single-precision floating point number.
TYPE_FLOAT = 0x04
# The 'data' holds a complex number encoding a dimension value, such as "100in".
TYPE_DIMENSION = 0x05
# The 'data' holds a complex number encoding a fraction of a container.
TYPE_FRACTION = 0x06

# Beginning of integer flavors...
TYPE_FIRST_INT = 0x10
# The 'data' is a raw integer value of the form n..n.
TYPE_INT_DEC = 0x10
# The 'data' is a raw integer value of the form 0xn..n.
TYPE_INT_HEX = 0x11
# The 'data' is either 0 or 1, for input "false" or "true" respectively.
TYPE_INT_BOOLEAN = 0x12

# Beginning of color integer flavors...
TYPE_FIRST_COLOR_INT = 0x1c
# The 'data' is a raw integer value of the form #aarrggbb.
TYPE_INT_COLOR_ARGB8 = 0x1c
# The 'data' is a raw integer value of the form #rrggbb.
TYPE_INT_COLOR_RGB8 = 0x1d
# The 'data' is a raw integer value of the form #argb.
TYPE_INT_COLOR_ARGB4 = 0x1e
# The 'data' is a raw integer value of the form #rgb.
TYPE_INT_COLOR_RGB4 = 0x1f

# ...end of integer flavors.
TYPE_LAST_COLOR_INT = 0x1f

# ...end of integer flavors.
TYPE_LAST_INT = 0x1f

# StringPool header flags
UTF8_FLAG = 1 << 0
SORTED_FLAG = 1 << 8

class StringPool:
    def __init__(self):
        self.stringCount = 0
        self.flag = 0
        self.entries = []

    def get_string(self, idx):
        if idx >= 0 and idx < self.stringCount:
            return self.entries[idx]
        else:
            return None

class XMLAttribute:
    def __init__(self, name, value):
        self.name = name
        self.value = value

class XMLNode:
    def __init__(self, name, isText=False):
        self.name = name
        self.attributes = []
        self.children = []
        self.isText = isText
        self.parent = None

    def addChild(self, node):
        self.children.append(node)
        node.parent = self

    def addAttr(self, attr):
        self.attributes.append(attr)

    def dump(self, depth=0, ns=None, indent="    "):
        prefix = indent * depth
        if self.isText:
            sys.stdout.write("%s%s\n" % (prefix, self.name))
            return
        sys.stdout.write('%s<%s' % (prefix, self.name))
        if ns:
            sys.stdout.write(' xmlns:%s="%s"' % (ns[0], ns[1]))
        # on same line for sole attribute
        if ns == None and len(self.attributes) == 1:
            attr = self.attributes[0]
            sys.stdout.write(' %s="%s"' % (attr.name, attr.value))
        else:
            for attr in self.attributes:
                sys.stdout.write('\n%s%s%s="%s"' % (prefix, indent, attr.name, attr.value))
        if self.children:
            sys.stdout.write('>\n')
            for node in self.children:
                node.dump(depth+1)
            sys.stdout.write('%s</%s>\n' % (prefix, self.name))
        else:
            sys.stdout.write(' />\n')


def error(msg):
    print >> sys.stderr, "Error: ", msg
    raise Exception(msg)

def print_debug(msg):
    print >> sys.stderr, msg

class AXMLParser:
    def __init__(self, data, outfile, debug=False):
        self.data = data
        self.outfile = outfile
        self.debug = debug

        self.namespaces = []
        self.savedns = []
        self.depth = 0
        self.strpool = StringPool()
        self.resids = []
        self.error = False
        self.curnode = XMLNode("")

    def parse_header(self, offset, debugenabled=False):
        data = self.data
        debug = self.debug and debugenabled
        if offset + HEADER_SIZE > len(data):
            error("incomplete chunk header at offset %d" % (offset))
        (htype, hsize, size) = unpack('<HHI', data[offset:offset+HEADER_SIZE])
        if debug:
            if htype in RES_MAP:
                tname = RES_MAP[htype]
            else:
                tname = ""
            print_debug("chunk (%#06x, %d, %d) offset %d %s" % (htype, hsize, size, offset, tname))
        if hsize < HEADER_SIZE or hsize + offset > len(data):
            error("invaid header size %d at offset %d with total size %d" % (hsize, offset, len(data)))
        if hsize > size:
            error("header size %d > chunk size %d at offset %d" % (hsize, size, offset))
        if size + offset > len(data):
            error("invaild chunk size %d at offset %d with total size %d" % (size, offset, len(data)))
        if (hsize | hsize) & 0x03:
            error("header size %d or chunk %d size not aligned by word at offset %d" % (hsize, size, offset))
        return (htype, hsize, size)
    
    def parse_resourcemap(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        resids = []
        for off in xrange(offset + hsize, offset + size, 4):
            (resid,) = unpack('<I', data[off:off+4])
            resids.append(resid)
        return resids
    
    def parse_stringpool(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        if hsize < SP_HEADER_SIZE:
            error("invalid StringPool header (%#06x, %d, %d) offset %d, min size is %d" % (htype, hsize, size, offset, SP_HEADER_SIZE))
        (stringCount, styleCount, flags, stringStart, styleStart) = unpack("<IIIII", data[offset+HEADER_SIZE:offset+SP_HEADER_SIZE])
        sp = StringPool()
        sp.stringCount = stringCount
        sp.styleCount = styleCount
        sp.flags = flags
        if debug:
            print_debug("StringPool (%#06x, %d, %d) offset %d, stringCount=%d, styleCount=%d, flags=%#x, stringStart=%d, styleStart=%d" % (htype, hsize, size, offset, stringCount, styleCount, flags, stringStart, styleStart))
        if stringCount > 0:
            if hsize + stringCount * 4 > size:
                error("Bad string block: string index array with %d items extends past chunk size %d" % (stringCount, size))
            off = offset + hsize
            for i in xrange(0, stringCount):
                (index,) = unpack('<I', data[off:off+4])
                sp.entries.append(index)
                off += 4
            if stringStart >= size:
                error("Bad string block: string pool starts at %d after chunk size %d" % (stringStart, size))
            if flags & UTF8_FLAG:
                charsize = 1
            else:
                charsize = 2
            if styleCount == 0:
                poolsize = size - stringStart
            else:
                if styleStart <= stringStart:
                    error("Bad string block: style block starts at %d before strings at %d" % (stringStart, styleStart))
                poolsize = styleStart - stringStart
            if poolsize == 0:
                error("Bad string block: stringCount is %d but pool size is 0" % (stringCount))
            pooloff = offset + stringStart
            for i in xrange(0, len(sp.entries)):
                off = sp.entries[i]
                if off + 1 > poolsize:
                    error("Bad string block: string #%d entry is at %d, past end at %d" % (i, off, poolsize))
                off += pooloff
                (strlen,) = unpack('<H', data[off:off+2])
                off += 2
                if strlen & 0x8000:
                    strlen = (strlen & ~0x8000) << 16 | unpack('<H', data[off:off+2])
                    off += 2
                if off + strlen >= poolsize + pooloff:
                    error("Bad string block: string #%d entry is at %d, past end at %d" % (i, off, poolsize))
                # if debug:
                #     print_debug("  string (%d len=%d, off=%d)" % (i, strlen, off))
                if flags & UTF8_FLAG:
                    error("UTF-8 encoded StringPool are not supported now")
                else:
                    strlen *= 2
                    s = data[off:off+strlen].decode('UTF-16LE').encode('UTF-8')
                sp.entries[i] = s
                if debug:
                    print_debug("    [%d] '%s'" % (i, s))
        return sp

    def parse_startns(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        off = offset + hsize
        (prefixid, uriid) = unpack('<II', data[off:off+8])
        prefix = self.strpool.get_string(prefixid)
        if prefix == None:
            error("namespace prefix #%d not found in pool" % (prefixid))
        uri = self.strpool.get_string(uriid)
        if uri == None:
            error("namespace uri #%d not found in pool" % (uriid))
        self.namespaces.append((prefix, uri))
        self.savedns.append((prefix, uri))
        if debug:
            print_debug("  NS %s=%s" % (prefix, uri))

    def parse_endns(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        off = offset + hsize
        (prefixid, uriid) = unpack('<II', data[off:off+8])
        prefix = self.strpool.get_string(prefixid)
        if prefix == None:
            error("namespace prefix #%d not found in pool" % (prefixid))
        uri = self.strpool.get_string(uriid)
        if uri == None:
            error("namespace uri #%d not found in pool" % (uriid))
        if len(self.namespaces) < 1:
            error("end namespace %s:%s without start namespace" % (prefix, uri))
        start = self.namespaces.pop()
        if start[0] != prefix or start[1] != uri:
            error("end namespace %s:%s unmatch start %s:%s" % (prefix, uri, start[0], start[1]))

    def get_namespace(self, nsid):
        ns = self.strpool.get_string(nsid)
        if ns:
            for item in self.namespaces:
                if ns == item[1]:
                    return item[0] + ":"
            return ns + ":"
        return ""
    
    def parse_starttag(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        off = offset + hsize
        (nsid, nameid, attrStart, attrSize, attrCount, idIndex, classIndex, styleIndex) = unpack('<IIHHHHHH', data[off:off+20])
        if debug:
            print_debug("  ELEMENT ns=%d name=%d, attrStart=%d, attrSize=%d, attrCount=%d, idIndex=%d, classIndex=%d, styleIndex=%d" % (nsid, nameid, attrStart, attrSize, attrCount, idIndex, classIndex, styleIndex))
        ns = self.get_namespace(nsid)
        name = self.strpool.get_string(nameid)
        if name == None:
            error("can not get element name #%d in pool" % (nameid))
        node = XMLNode(ns + name)
        self.curnode.addChild(node)
        self.curnode = node
        if debug:
            print_debug("  ELEMENT %s" % (node.name))
        off = offset + hsize + attrStart
        for i in xrange(0, attrCount):
            (nsid, nameid, valueid, a_size, a_res0, a_type, a_data) = unpack('<IIIHBBI', data[off:off+20])
            if debug:
                print_debug("    ATTR ns=%d, name=%d, value=%d, size=%d, type=0x%02x, data=%d" % (nsid, nameid, valueid, a_size, a_type, a_data))
            off += attrSize
            ns = self.get_namespace(nsid)
            name = self.strpool.get_string(nameid)
            if name == None:
                error("can not get attribute name #%d in pool" % (nameid))
            if a_type == TYPE_NULL:
                value = "(null)"
            elif a_type == TYPE_REFERENCE:
                value = "@0x%x" % (a_data)
            elif a_type == TYPE_ATTRIBUTE:
                value= "?0x%x" % (a_data)
            elif a_type == TYPE_STRING:
                value = self.strpool.get_string(valueid)
                if value == None:
                    error("can not get string attribute value #%d in pool" % (valueid))
            elif a_type == TYPE_INT_DEC:
                value = "%d" % (a_data)
            elif a_type == TYPE_INT_HEX:
                value = "0x%x" % (a_data)
            elif a_type == TYPE_INT_BOOLEAN:
                value = a_data == 0 and "false" or "true"
            else:
                value = "(type 0x%x)0x%x" % (a_type, a_data)
            attr = XMLAttribute(ns + name, value)
            node.addAttr(attr)
            if debug:
                print_debug("    ATTR %s=%s" % (attr.name, attr.value))

    def parse_endtag(self, offset):
        data = self.data
        debug = self.debug
        if self.curnode.parent == None:
            error("end tag without matched start tag  (0x%04x, %d, %d) offset %d" % (htype, hsize, size, offset))
        self.curnode = self.curnode.parent

    def parse_textnode(self, offset):
        data = self.data
        debug = self.debug
        (htype, hsize, size) = self.parse_header(offset)
        off = offset + hsize
        (textid,) = unpack('<I', data[off:off+4])
        text = self.strpool.get_string(textid)
        if text == None:
            text = ""
        node = XMLNode(text, True)
        self.curnode.addChild(node)

    def parsexml(self):
        data = self.data
        offset = 0
        if len(data) < 8:
            error("invalid binary xml ( size < 8)")
        (htype, hsize, size) = self.parse_header(offset, True)
        if htype != RES_XML_TYPE:
            error("invalid binary xml with header type 0x%04x (expect %#06x)" % (htype, RES_XML_TYPE))
        offset += hsize
        depth = 0
        while offset < len(data):
            (htype, hsize, size) = self.parse_header(offset, True)
            if htype == RES_STRING_POOL_TYPE:
                # if strpool:
                #     error("duplicate StringPool (0x%04x, %d, %d) offset %d" % (htype, hsize, size, offset))
                self.strpool = self.parse_stringpool(offset)
            elif htype == RES_XML_RESOURCE_MAP_TYPE:
                self.resids = self.parse_resourcemap(offset)
            elif htype >= RES_XML_FIRST_CHUNK_TYPE and htype <= RES_XML_LAST_CHUNK_TYPE:
                if hsize < NODE_HEADER_SIZE:
                    error("invalid tree node header (0x%04x, %d, %d) offset %d, min size is %d" % (htype, hsize, size, offset, NODE_HEADER_SIZE))
                if htype == RES_XML_START_ELEMENT_TYPE:
                    self.parse_starttag(offset)
                elif htype == RES_XML_END_ELEMENT_TYPE:
                    self.parse_endtag(offset)
                elif htype == RES_XML_START_NAMESPACE_TYPE:
                    self.parse_startns(offset)
                elif htype == RES_XML_END_NAMESPACE_TYPE:
                    self.parse_endns(offset)
                elif htype == RES_XML_CDATA_TYPE:
                    self.parse_textnode(offset)
            else:
                print_debug("Skipping unknown chunk: (0x04x, %d, %d) offset %d" % (htype, hsize, size, offset))
            offset += size

        if len(self.curnode.children) > 1:
            error("multiple element at toplevel")
        root = self.curnode.children[0]
        print '<?xml version="1.0" encoding="utf-8"?>'
        if self.savedns:
            root.dump(0, self.savedns[-1])
        else:
            root.dump(0)

class ResourceParser(AXMLParser):
    def __init__(self, data, outfile, debug=False):
        AXMLParser.__init__(self, data, outfile, debug)

    def parse_package(offset=0):
        data = self.data
        debug = self.debug
        (htype, hsize, size, pkgid) = unpack('<HHII', data[offset:offset+12])

        if pkgid < 1 or pkgid >= 256:
            print_debug("Skins not supported (package id: %d)" % (pkgid))
            return
        off = offset + 12
        # package name are UTF-16 encoded with NULL terminated, 128 bytes at most
        end = off
        while end < off + 128 and data[end:end+2] != '\x00\x00':
            end += 2
        pkgname = data[off:end].decode('UTF-16LE')
        off += 128
        (typeStrings, lastPublicType, keyStrings, lastPublicKey) = unpack('<IIII', data[off:off+16])
        off += 16
        off = offset + hsize
        while off + 8 <= len(data):
            (htype, hsize, size) = self.parse_header(offset, True)
            if htype == RES_TABLE_TYPE_SPEC_TYPE:
                pass
            elif htype == RES_TABLE_TYPE_TYPE:
                pass
            else:
                print_debug("Unknown chunk type 0x%04x in package chunk" % (htype))
            
    def parse_resources(self):
        offset = 0
        data = self.data
        debug = self.debug

        if len(data) < 12:
            error("invalid resource table file ( size < 12)")
        (htype, hsize, size) = self.parse_header(offset, True)
        if htype != RES_TABLE_TYPE:
            error("invalid binary xml with header type 0x%04x (expect %#04x)" % (htype, RES_TABLE_TYPE))
        (pkg_count,) = unpack('<I', data[offset+8:offset+12])
        offset += hsize
        while offset < len(data):
            (htype, hsize, size) = self.parse_header(offset, True)
            if htype == RES_STRING_POOL_TYPE:
                if self.strpool:
                    print_debug("duplicate StringPool (0x%04x, %d, %d) offset %d" % (htype, hsize, size, offset))
                else:
                    self.strpool = self.parse_stringpool(offset)
            elif htype == RES_TABLE_PACKAGE_TYPE:
                self.parse_package(offset)
            else:
                print_debug("Skipping unknown chunk: (0x04x, %d, %d) offset %d" % (htype, hsize, size, offset))
            offset += size
