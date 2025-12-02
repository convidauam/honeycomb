from collections import namedtuple
from collections.abc import Sequence
from persistent import Persistent
from pyramid import traversal
import numpy as np
from scipy import spatial


AXES_LABELS_DEFAULT = 'problem_solving', 'integration', 'abstract_thinking'
AXES_DEFAULT_VALUE = 0

JellyPack = namedtuple('JellyPack', AXES_LABELS_DEFAULT, defaults=[AXES_DEFAULT_VALUE] * len(AXES_LABELS_DEFAULT))


class CellBuilder(Persistent):
    "Helper class to set cell properties"
    __axes__ = AXES_LABELS_DEFAULT

    @staticmethod
    def fill_cell(cell, *values, **kwvalues):
        cell.__axes__ = JellyPack(*values, **kwvalues)

    def set_walls(self, cell, limits):
        cell.__limits__ = {k:limits[k] for k in limits if k in self.__axes__}

    @staticmethod
    def set_badge(cell, badge):
        cell.__badge__ = badge

    @staticmethod
    def has_access(cell, user):
        if hasattr(cell, '__limits__'):
            for k,v in cell.__limits__.items():
                if user.get_stats(k) < v:
                    return False
        return True


class HoneycombExplorer(Persistent):
    "Helper to create, update and employ the honeycomb node distance matrix"
    def __init__(self, honeycomb):
        self.__hc__ = honeycomb
        self.names = []
        self.matrix = None

    def update_matrix(self):
        root = traversal.find_root(self.__hc__)
        names = []
        coords = []
        for item in root.__nodes__.items():
            path = traversal.resource_path_tuple(item[1])
            if path and path[1] == self.__hc__.__name__:
                if getattr(item[1], '__axes__', None):
                    names.append(item[0])
                    coords.append(item[1].__axes__)
        print(coords)
        self.matrix = spatial.distance_matrix(np.array(coords), np.array(coords))
        self.names = names