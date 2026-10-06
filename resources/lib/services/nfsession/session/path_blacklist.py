# -*- coding: utf-8 -*-
"""
    Copyright (C) 2026 plugin.video.netflix
    Netflix path blacklist

    Tracks Falcor paths that Netflix has answered with an error, so they can
    be skipped in subsequent requests of the same session.

    SPDX-License-Identifier: MIT
    See LICENSES/MIT.md for more information.
"""


class PathBlacklist:
    """In-memory set of path keys known to be rejected by the Netflix API"""

    def __init__(self):
        """Create an empty blacklist"""
        self._blocked = set()

    def is_blocked(self, path_key):
        """Return True if the given path key was previously blocked"""
        return path_key in self._blocked

    def block(self, path_key):
        """Mark a path key as blocked"""
        self._blocked.add(path_key)

    def blocked_count(self):
        """Return the number of blocked path keys"""
        return len(self._blocked)

    def clear(self):
        """Remove all blocked path keys"""
        self._blocked.clear()

    def merge(self, json_graph):
        """Recursively scan a JSON Graph response and record every node
        Netflix answered with an '$error' as a blocked response key path"""
        self._scan(json_graph, [])

    def _scan(self, node, key_path):
        """Walk a JSON Graph node and block the key path of every '$error' node

        Keys starting with '$' are JSON Graph metadata ('$type', '$ref', ...) and
        are no part of the path to the node, so they are not accumulated.

        :param node: the JSON Graph node to inspect
        :type node: dict
        :param key_path: the keys leading to the given node
        :type key_path: list
        """
        if not isinstance(node, dict):
            return
        if '$error' in node:
            self.block('/'.join(key_path))
            return
        for key, value in node.items():
            if key.startswith('$'):
                continue
            self._scan(value, key_path + [str(key)])


#: Session scoped blacklist of the paths rejected by Netflix
PATH_BLACKLIST = PathBlacklist()
