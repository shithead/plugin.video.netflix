# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Baseline tests for the Falcor path helpers
"""
import resources.lib.utils.api_paths as apipaths
from resources.lib.services.nfsession.session.path_requests import _set_range_selector


def test_build_paths_concatenates_base_and_partial():
    """
    Each partial path is appended to the base path

    build_paths is a shallow concatenation (api_paths.py:149), so a real
    constant such as SEASONS_PARTIAL_PATHS lands flat in the built path.
    _set_range_selector locates its placeholder with path.index(), which
    only searches the top level, so this flat shape is the precondition for
    the range selector tests below to mean anything.
    """
    assert apipaths.build_paths(['videos', 123], [['title'], ['summary']]) == [
        ['videos', 123, 'title'],
        ['videos', 123, 'summary'],
    ]
    assert apipaths.build_paths(['videos', 1], [apipaths.SEASONS_PARTIAL_PATHS[0]]) == [
        ['videos', 1, 'seasonList', apipaths.RANGE_PLACEHOLDER, 'summary']
    ]


def test_jgraph_get_resolves_atom():
    """An atom node yields its 'value'"""
    assert apipaths.jgraph_get('title', {'title': {'$type': 'atom', 'value': 'The Show'}}) == 'The Show'


def test_jgraph_get_resolves_ref():
    """A ref node is followed into the full data"""
    data = {
        'videos': {'123': {'title': {'$type': 'atom', 'value': 'Movie'}}},
        'ref': {'$type': 'ref', 'value': ['videos', '123', 'title']},
    }
    assert apipaths.jgraph_get('ref', data) == 'Movie'


def test_jgraph_get_list_converts_indexed_refs():
    """
    jgraph_get_list returns an index keyed dict of the resolved list items

    The 'summary' length attribute decides how many items are read, so the
    trailing empty atom of the fixture data is never touched.
    """
    data = {
        'lists': {
            'summary': {'$type': 'atom', 'value': {'length': 2}},
            '0': {'$type': 'ref', 'value': ['videos', '1', 'summary']},
            '1': {'$type': 'atom', 'value': {'id': '2'}},
            '2': {'$type': 'atom', 'value': None},
        },
        'videos': {'1': {'summary': {'$type': 'atom', 'value': {'id': '1'}}}},
    }
    assert apipaths.jgraph_get_list('lists', data) == {
        0: {'id': '1'},
        1: {'id': '2'},
    }


def test_jgrapgh_len_stops_at_first_atom():
    """Counting stops at the first atom, which signals the end of the list"""
    data = {'0': {'$type': 'ref', 'value': ['a']}, '1': {'$type': 'atom', 'value': 1}}
    assert apipaths.jgrapgh_len(data) == 1


def test_set_range_selector_replaces_placeholder():
    """RANGE_PLACEHOLDER is swapped for the concrete range dict"""
    paths = [['videos', 1, 'seasonList', apipaths.RANGE_PLACEHOLDER, 'summary']]
    assert _set_range_selector(paths, 0, 10) == [
        ['videos', 1, 'seasonList', {'from': 0, 'to': 10}, 'summary']
    ]


def test_set_range_selector_replaces_placeholder_in_built_paths():
    """
    The placeholder of a real partial path constant survives into the request

    This couples the two halves: build_paths flattens SEASONS_PARTIAL_PATHS,
    and _set_range_selector then finds its placeholder. If a future change
    nested the partial, this test fails along with the flat shape assertion
    in test_build_paths_concatenates_base_and_partial.
    """
    paths = apipaths.build_paths(['videos', 1], [apipaths.SEASONS_PARTIAL_PATHS[0]])
    assert _set_range_selector(paths, 0, 10) == [
        ['videos', 1, 'seasonList', {'from': 0, 'to': 10}, 'summary']
    ]


def test_set_range_selector_does_not_mutate_input():
    """The original paths keep their placeholder"""
    paths = [['videos', 1, 'seasonList', apipaths.RANGE_PLACEHOLDER, 'summary']]
    _set_range_selector(paths, 0, 10)
    assert paths[0][3] == apipaths.RANGE_PLACEHOLDER


def test_set_range_selector_keeps_nested_placeholder():
    """
    A placeholder below the top level of a path is not replaced

    path.index() raises ValueError, which the except branch swallows, so
    the path comes back unchanged. No current call site nests a partial
    around a placeholder: every RANGE_PLACEHOLDER in production sits at the
    top level. The risk here is prospective, not live.
    """
    paths = [['videos', 1, ['seasonList', apipaths.RANGE_PLACEHOLDER, 'summary']]]
    assert _set_range_selector(paths, 0, 10) == [
        ['videos', 1, ['seasonList', apipaths.RANGE_PLACEHOLDER, 'summary']]
    ]
