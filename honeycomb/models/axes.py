"""Defines data structures for node coordinates and implements helper classes to create, update and employ the honeycomb node distance matrix or individual node coordinates."""

from collections import namedtuple
from collections.abc import Sequence
from persistent import Persistent
from pyramid import traversal
import numpy as np
from scipy import spatial
from sklearn.manifold import MDS


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
        "Iterates through the beehive nodes and recalculates distance matrix based on the axes values of nodes belonging to the chosen Honeycomb"
        root = traversal.find_root(self.__hc__)
        names = []
        coords = []
        for node_id, node in root.__nodes__.items():
            path = traversal.resource_path_tuple(node)
            if path and path[1] == self.__hc__.__name__:
                if getattr(node, '__axes__', None):
                    names.append(node)
                    coords.append(node.__axes__)
        self.matrix = spatial.distance_matrix(np.array(coords), np.array(coords))
        self.names = names
    def reduction_2d(self):
        "This use the MDS dimentional reduction trough sklearn function defined"
        if self.matrix is None:
            self.update_matrix()
        reduction= MDS(n_components=2, dissimilarity='precomputed', random_state=42)
        "In reduction function precomputed indicates the property of matrix distances and no the nodes points in the space, while we use the random state to preserve the correct position of all nodes"
        coords_2d = mds.fit_transform(self.update_matrix)
        return coords_2d