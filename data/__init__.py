import paths
import os
import os.path
import subprocess
import tempfile
import codecs
import re

try:
    import lxml.etree
except ImportError:
    print 'warning, lxml not installed'
    pass

from PIL import Image

class ConvertibleMap:
    def __init__(self, dir, extension):
        self.dir = os.path.join(paths.root, dir)
        self.ext = extension
        ee = '.'+extension.lower()
        self.files = [p[:-len(extension)-1] for p in
                      os.listdir(self.dir) if p.lower().endswith(ee)]
        self.fileset = set(p.lower() for p in self.files)
        self.loaded = {}

    def keys(self):
        return self.files

    def __contains__(self, k):
        return k.lower() in self.fileset

    def __getitem__(self, k):
        #import pdb; pdb.set_trace()
        kk = k.lower()
        if kk not in self.fileset:
            raise KeyError(k)
        if kk in self.loaded:
            return self.loaded[kk]
        lookupname = k+'.'+self.ext
        readpath = os.path.join(self.dir, lookupname)
        self.loaded[kk] = self.raw_load(readpath)
        return self.loaded[kk]

    def raw_load(self, readpath):
        with open(readpath) as infile:
            firstline = infile.readline().strip()
            if firstline == 'TXT':
                return list(infile)
        if firstline == 'BIN':
            temphandle, temppath = tempfile.mkstemp('.sins.txt')
            os.close(temphandle)
            try:
                root, ext = os.path.splitext(readpath)
                assert ext
                args = [paths.converter, ext[1:], readpath, temppath, 'txt']
                retcode = subprocess.call(args)
                assert retcode == 0
                with codecs.open(temppath, encoding='utf_8_sig') as infile:
                    tempfirstline = infile.readline().strip()
                    assert tempfirstline == 'TXT'
                    return list(infile)
            finally:
                # Clean up the temporary file
                if os.path.exists(temppath):
                    os.remove(temppath)
        else:
            assert firstline == 'TXT'

class XMLConvertibleMap:
    def __init__(self, cm):
        self.cm = cm

    def keys(self):
        return self.cm.keys()

    def __contains__(self, k):
        return k in self.cm

    def __getitem__(self, k):
        return as_element(self.cm[k])

def xcm(dir, ext):
    return XMLConvertibleMap(ConvertibleMap(dir, ext))

def __element_item_type(s):
    if s == 'TRUE' or s == 'FALSE':
        return 'bool', s
    if len(s) >= 2 and s[0]=='"' and s[-1]=='"':
        return 'str', s[1:-1]
    try:
        val = float(s)
        return 'number', s
    except ValueError:
        return 'unknown', s

def as_element(d):
    """Create a lxml element 'root' of a data file.
    
    The primary purpose of this conversion is to enable easy extraction of file values through xpath."""
    # Load this within the function.
    root = lxml.etree.Element('root') # Universal root.
    # Easy to keep track of tree structure with a last-seen-on-this-level list.
    elements = [root]
    last_level = 0
    rec = re.compile(r'(\t*)([^\s:]*)(?::(\S+))?(?:( ?)([^\r\n]*))')
    for line in d:
        # Match the line, and build the associated element.
        m = rec.match(line)
        if m == None:
            print 'failed to match', line,
        tabs, item_name, item_index, space, item_value = m.groups()
        level = len(tabs)+1
        # Blank item names exist in some places like meshes.
        e = lxml.etree.Element(item_name if item_name else 'EMPTY')
        if item_index:
            e.attrib['index'] = item_index
        if item_value:
            t, v = __element_item_type(item_value)
            # Let's suppose the default type is str.
            if t != 'str': e.attrib['type'] = t
            e.text = v
        # We can go one deeper, but not many deeper
        assert level <= last_level+1
        if level >= len(elements):
            # The novel level must exist.
            assert level == len(elements)
            elements.append(e)
        # Update the structures with this element.
        elements[level-1].append(e)
        elements[level] = e
        last_level = level
    return root

class TextureMap(ConvertibleMap):
    def raw_load(self, readpath):
        #return super(TextureMap, readpath).raw_load()
        return Image.open(readpath, 'r')

entity = xcm('GameInfo', 'entity')
#constant = xcm('GameInfo', 'constants')
mesh = xcm('Mesh', 'mesh')
particle = xcm('Particle', 'particle')
brush = xcm('Window', 'brushes')
string = xcm('String', 'str')
gsd = xcm('GameInfo', 'galaxyScenarioDef')['GalaxyScenarioDef']
gpc = xcm('GameInfo', 'constants')['Gameplay']

if __name__=='__main__':
    # Test code
    mm = mesh['Frigate_PhaseEnvoy']
    #print entity.fileset
    d = entity['PlayerPsiLoyalist']
    #e = as_element(d)
    #print lxml.etree.tostring(e, pretty_print=True)
