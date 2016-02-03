import glob
import os.path

root = r'D:\SSDOffload\Program Files (x86)\Steam\SteamApps\common'+\
    r'\Sins of a Solar Empire Rebellion'
gameinfo = os.path.join(root, 'GameInfo')
converter = glob.glob(os.path.join(root, 'ConvertData*.exe'))
if len(converter) != 1:
    raise "Could not find single convert data executable: %s" % converter
converter = converter[0]
