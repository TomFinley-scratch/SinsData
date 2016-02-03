import collections
import re

import lxml.etree
from PIL import Image

import data

Price = collections.namedtuple('Price', 'credits metal cystal')
Durability = collections.namedtuple('Durability', 'hull shield dhull dshield armor mit')
LinearLevel = collections.namedtuple('LinearLevel', 'start_value increase_per_level')

def pps(e):
    """Convenience method to return the pretty print string of a element."""
    return lxml.etree.tostring(e, pretty_print=True)

def pp(e):
    print pps(e),

class EntityItem(object):
    strings = data.string['English']

    def __init__(self, name):
        self.name = name
        self.__element = None

    @property
    def element(self):
        # Lazy loading of the backing data file.
        if self.__element == None:
            self.__element = data.entity[self.name]
        return self.__element

    @property
    def entity_type(self):
        return self._get_single_value('entityType')

    def _get_string_named(self, name):
        n = self._get_string_named_none(name)
        if n is None:
            raise KeyError('could not find StringInfo for %s' % n)
        return n

    def _get_string_named_none(self, name):
        n = self._get_single_value_none(name)
        result = EntityItem.strings.xpath('StringInfo[ID="%s"]/Value' % n)
        if len(result) == 0: return None
        if len(result) > 1:
            raise KeyError('multiple StringInfos for %s' % n)
        return result[0].text

    def _get_single_value(self, path, *funcs):
        v = self._get_single_value_none(path, *funcs)
        if v is None:
            raise KeyError('no value for %s' % path)
        return v

    def _get_single_value_none(self, path, *funcs):
        e = self.element.xpath(path)
        if len(e) == 0: return None
        if len(e) > 1:
            raise KeyError('path %s yielded %d results' % (path, len(e)))
        retval = e[0].text
        for f in funcs:
            retval = f(retval)
        return retval

    def _get_leveled_value(self, path):
        e = self.element.xpath(path)
        if len(e)!=1:
            raise KeyError('path %s yielded %d results' % (path, len(e)))
        e = e[0]
        s = e.xpath('./StartValue')
        if not s: raise KeyError('path %s did not have StartValue', path)
        start = float(s[0].text)
        s = e.xpath('./ValueIncreasePerLevel')
        if not s: raise KeyError('path %s did not have ValueIncreasePerLevel', path)
        delta = float(s[0].text)
        return LinearLevel(start, delta)

class Player(EntityItem):
    prefix = 'Player'
    races = ['Tech', 'Phase', 'Psi']
    factions = ['Loyalist', 'Rebel']

    def __init__(self, name):
        super(Player, self).__init__(name)

    def __repr__(self):
        return '<Player %s>' % self.name

    def __fetch_entities(self, type, page=None):
        if page != None:
            result = self.element.xpath("entities/%s/Page[@index='%d']/entityDefName/text()" % (type, page))
        else:
            result = self.element.xpath("entities/%s/NotOnPage/entityDefName/text()|entities/%s/entityDefName/text()" % (type, type))
        return result

    @property
    def parse_prefix(self):
        """The parse prefix for this player, e.g., TECH/PSI/PHASE."""
        result = self.element.xpath("raceNameParsePrefix/text()")
        if len(result)!=1:
            raise KeyError("Bad parse prefix")
        return str(result[0])

    @property
    def frigates(self):
        """Ships considered frigates."""
        e = self.__fetch_entities('frigateInfo', 0)
        return [Ship(i) for i in e]

    @property
    def cruisers(self):
        """Ships considered cruisers (technically a subclass of frigates)."""
        e = self.__fetch_entities('frigateInfo', 1)
        return [Ship(i) for i in e]

    @property
    def strikecraft(self):
        """All strike craft, including fighters, bombers, and for Advent the mine layers."""
        # I have not yet found the file or entry that associates a player
        # with a strikecraft type.
        m = re.compile("^fighter"+self.parse_prefix, re.I)
        matches = [k for k in data.entity.keys() if m.match(k)]
        return [NoBuildShip(k) for k in matches]

    @property
    def autos(self):
        """Ships automatically built, e.g., trade/refinery/constructor ships."""
        e = self.__fetch_entities('frigateInfo')
        return [Ship(i) for i in e]

    @property
    def capitals(self):
        """Ships considered capital ships."""
        e = self.__fetch_entities('capitalShipInfo', 0)
        return [CapitalShip(i) for i in e]

    @property
    def titan(self):
        """The titan ship for this player."""
        e = self.__fetch_entities('titanInfo', 0)
        if len(e) == 0: return None
        assert len(e) == 1
        return CapitalShip(e[0])

    @property
    def civ_mods(self):
        """Logistic modules available to this player."""
        e = self.__fetch_entities('planetModuleInfo', 0)
        return [Module(i) for i in e]

    @property
    def mil_mods(self):
        """Tactical modules available to this player."""
        e = self.__fetch_entities('planetModuleInfo', 1)
        return [Module(i) for i in e]

    @property
    def starbase(self):
        """The starbase for this player, if one exists."""
        e = self.__fetch_entities('starBaseInfo')
        if len(e) == 0: return None
        assert len(e) == 1
        return Starbase(e[0])

class GameObject(EntityItem):
    """An object like a module or ship that exists in the game."""
    def __init__(self, name):
        super(GameObject, self).__init__(name)

    __brushprefix = ['picture', 'mainviewicon', 'hudicon']

    @property
    def picture_brush(self):
        return self.__get_brush_named('picture')

    @property
    def mainview_brush(self):
        return self.__get_brush_named('mainViewIcon')

    @property
    def smallhud_brush(self):
        return self.__get_brush_named('smallHudIcon')

    def __get_brush_named(self, name):
        n = self._get_single_value_none(name)
        # Some of these brushes are not specified in the entity file, and that
        # is fine.  So we simply return none here.  What is not fine is for a
        # brush to be indicated in the entity file, but not appear in the
        # corresponding brush files.
        if n == None: return None
        nlower = n.lower()
        firstpart = nlower[:nlower.index('_')] if '_' in nlower else nlower
        for prefix in self.__brushprefix:
            if prefix in firstpart:
                break
        else:
            raise KeyError('Could not determine brush location of %s' % n)
        prefix, query = prefix + '-', 'brush[name="%s"]' % n
        brushfiles = [f for f in data.brush.keys() if f.lower().startswith(prefix)]
        result = [r for bd in (data.brush[f] for f in brushfiles) for r in bd.xpath(query)]
        if len(result)!=1:
            raise KeyError('No single match for brush named %s, found %d' % (n, len(result)))
        return result[0]

class StaticGameObject(GameObject):
    """An object that excludes starbases."""
    @property
    def display_name(self):
        return self._get_string_named('NameStringID|nameStringID')

    @property
    def description(self):
        """Returns the detailed description."""
        return self._get_string_named_none('DescriptionStringID')

    @property
    def price(self):
        """Returns price of this item in credits/metal/crystal."""
        # For some reason these are encoded as floats in the files.
        credits = int(float(self.element.xpath('basePrice/credits')[0].text))
        metal = int(float(self.element.xpath('basePrice/metal')[0].text))
        crystal = int(float(self.element.xpath('basePrice/crystal')[0].text))
        return Price(credits, metal, crystal)

    @property
    def experience(self):
        """The number of experience points from destroying this item."""
        return self._get_single_value('ExperiencePointsForDestroying|experiencePointsForDestroying', float)
    
    @property
    def armor(self):
        """The armor type of this item."""
        return self._get_single_value('armorType')

    _durability_keys = \
        ['MaxHullPoints|maxHullPoints', 'MaxShieldPoints',
         'HullPointRestoreRate|hullPointRestoreRate',
         'ShieldPointRestoreRate', 'BaseArmorPoints|armorPoints|ArmorPointsFromExperience',
         'maxShieldMitigation|maxMitigation']

    @property
    def durability(self):
        vals = [self._get_single_value_none(k, float) for k in self._durability_keys]
        return Durability(*vals)

class Module(StaticGameObject):
    """A static structure within a gravity well."""
    @property
    def build_time(self):
        """Returns the time in seconds it takes to build this."""
        return self._get_single_value('baseBuildTime', float)

    @property
    def slot_type(self):
        """The type of slots this item takes, Logistic or Tactical."""
        return self._get_single_value('planetUpgradeSlotType')

    @property
    def slots(self):
        """How many slots this item takes."""
        return self._get_single_value('planetUpgradeSlotCount', float, int)

    def __repr__(self):
        return '<Module %s>' % self.name

class Ship(StaticGameObject):
    def __repr__(self):
        return '<Ship %s>' % self.name

    @property
    def build_time(self):
        """Returns the time in seconds it takes to build this."""
        return self._get_single_value('BuildTime', float)

    @property
    def supply(self):
        """The amount of fleet supply this ship takes."""
        return self._get_single_value('slotCount', float, int)

    @property
    def has_levels(self):
        """Whether this is a ship with multiple levels."""
        v = self._get_single_value_none('hasLevels')
        if v == None: return None
        return v.lower()=='true'

    def _get_explicit_leveled_value(self, path):
        e = self.element.xpath(path)
        if len(e)!=1:
            raise KeyError('path %s yielded %d results' % (path, len(e)))
        e = e[0]
        s = e.xpath('./Level')
        s.sort(key = lambda x: int(x.attrib['index']))
        return [float(e.text) for e in s]

    @property
    def experience(self):
        if self.has_levels:
            return self._get_explicit_leveled_value('ExperiencePointsForDestroying')
        return super(Ship, self).experience

    @property
    def durability(self):
        if self.has_levels:
            vals = [self._get_explicit_leveled_value(k) for k in self._durability_keys]
            return Durability(*vals)
        return super(Ship, self).durability

class CapitalShip(Ship):
    @property
    def experience(self):
        return cap_experience(False)

    @property
    def durability(self):
        vals = [self._get_leveled_value(k) for k in self._durability_keys]
        return Durability(*vals)

class NoBuildShip(Ship):
    @property
    def build_time(self):
        return None

    @property
    def price(self):
        return None

    @property
    def supply(self):
        return None

class Starbase(GameObject):
    def __repr__(self):
        return '<Starbase %s>' % self.name

def cap_experience(titan):
    dat = data.gpc.xpath(\
        'GameplayConstants/' + \
        ('TitanData' if titan else 'CapitalShipData') + \
        '/ExperienceLevelData')
    return dat

def brush_image(brush):
    """Given a brush definition, return a corresponding PIL image."""
    pass

if __name__=='__main__':
    def test_one(obj, toprint=True):
        """Tests an object minimally by merely accessing its attributes.
        
        The intent of this test is to weed out all the little inconsistencies in the
        entity files, between different types of objects and even with the same types
        of objects.  (E.g., envoy vessels have some of their traits in totally different
        files than every other frigate.)"""
        for n in dir(obj):
            if n.startswith('_'): continue
            try:
                nn = getattr(obj, n)
            except:
                print 'WARNING: failure on', obj, 'attribute', n
                raise
            if toprint:
                print n, ':::', nn

    def test_player(p):
        """Tests the object of every aspect of the player."""
        # Test the player.
        def t(pp):
            test_one(pp, False)
        t(p)
        for s in p.frigates: t(s)
        for s in p.cruisers: t(s)
        for s in p.strikecraft: t(s)
        for s in p.autos: t(s)
        t(p.starbase)
        t(p.titan)

    players = [Player(i.text) for i in data.gsd.xpath('playerType/entityDefName')]
    for i in players:
        print i.parse_prefix, i

    print players[0].capitals[0].durability



    if False:
        for p in players:
            print 'testing', p
            test_player(p)
        print 'done testing'
