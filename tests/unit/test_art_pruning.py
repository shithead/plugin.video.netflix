# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Verify that retired artwork paths are neither requested nor parsed
"""
import ast
import importlib

import resources.lib.kodi.infolabels as infolabels
import resources.lib.utils.api_paths as apipaths
import resources.lib.utils.api_requests as api_requests
from resources.lib.common import VideoId
from resources.lib.services.nfsession import nfsession_ops
from resources.lib.services.nfsession.directorybuilder import dir_path_requests

# The Falcor artwork nodes Netflix removed from its schema. `pathEvaluator` is
# all-or-nothing per batch, so one surviving occurrence 404s the whole request.
RETIRED_ART_NODES = ('boxarts', 'storyArt', 'artWorkByType', 'interestingMoment')

# The modules that assemble Falcor paths out of ART_PARTIAL_PATHS. None of them may
# hold that name in its own namespace: `from .api_paths import ART_PARTIAL_PATHS`
# binds the list object at import time, so emptying the constant afterwards leaves
# every bound name pointing at the old four-entry list and the 404 comes back.
ART_PATH_CONSUMERS = (
    'resources.lib.services.nfsession.directorybuilder.dir_path_requests',
    'resources.lib.utils.api_requests',
    'resources.lib.services.nfsession.nfsession_ops',
    'resources.lib.kodi.infolabels',
)

# The modules whose source is inspected for surviving artwork node names. A literal
# anywhere in them would put a retired node back into a request batch.
ART_PATH_SOURCES = ART_PATH_CONSUMERS + ('resources.lib.utils.api_paths',)

# Partial-path sets of the api_paths module that concatenate ART_PARTIAL_PATHS.
ART_PATH_SETS = (
    apipaths.VIDEO_LIST_PARTIAL_PATHS,
    apipaths.SEASONS_PARTIAL_PATHS,
    apipaths.EPISODES_PARTIAL_PATHS,
    apipaths.TRAILER_PARTIAL_PATHS,
)

# Canned JSON Graph response, just rich enough for the data_types wrappers that
# DirectoryPathRequests builds from the recorded batches.
CANNED_RESPONSE = {
    'locos': {'ROOT1': {'componentSummary': {'$type': 'atom', 'value': {'length': 0}}}},
    'videos': {'80057281': {'seasonList': {}}},
    'seasons': {'80057283': {'episodes': {}}},
}


def _retired_art_nodes(paths):
    """
    Return every retired artwork node name reached by a batch of Falcor paths

    A path element is either a scalar (node name, id, range dict) or a nested list
    of field names, so both levels are inspected.

    :param paths: a batch of Falcor paths, as sent to pathEvaluator
    :type paths: list
    :return: the retired node names occurring in the batch
    :rtype: list
    """
    found = []
    for path in paths:
        for element in path:
            candidates = element if isinstance(element, list) else [element]
            found.extend(name for name in candidates if name in RETIRED_ART_NODES)
    return found


def _docstring_constants(tree):
    """
    Return the set of string constants that serve as a docstring

    :param tree: the parsed source of a module
    :type tree: ast.Module
    :return: the ids of the docstring constants of the module
    :rtype: set
    """
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    return docstrings


def _retired_art_literals(module_path):
    """
    Return the retired artwork node names still spelled as a literal in a module

    Comments and docstrings are exempt, because they document the removal and never
    reach the API. Parsing the source instead of splitting lines at '#' also means
    a '#' inside a string literal cannot mask a surviving reference.

    :param module_path: the dotted path of the module to inspect
    :type module_path: str
    :return: the (line number, node name) pairs that must not be there
    :rtype: list
    """
    module = importlib.import_module(module_path)
    with open(module.__file__, encoding='utf-8') as handle:
        tree = ast.parse(handle.read(), filename=module_path)
    docstrings = _docstring_constants(tree)
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in RETIRED_ART_NODES
            and id(node) not in docstrings]


def _art_partial_paths_importers(module_path):
    """
    Return the lines on which a module imports ART_PARTIAL_PATHS by name

    Any alias is reported, because `from .api_paths import ART_PARTIAL_PATHS as ART`
    binds the same stale list object as the plain form.

    :param module_path: the dotted path of the module to inspect
    :type module_path: str
    :return: the line numbers of the offending import statements
    :rtype: list
    """
    module = importlib.import_module(module_path)
    with open(module.__file__, encoding='utf-8') as handle:
        tree = ast.parse(handle.read(), filename=module_path)
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and any(alias.name == 'ART_PARTIAL_PATHS' for alias in node.names)]


class _RecordingSession:
    """Records every path batch a DirectoryPathRequests builds and answers canned data"""

    def __init__(self):
        """Start with an empty batch log"""
        self.batches = []

    def path_request(self, paths=None, **kwargs):
        """
        Record a path batch and answer with canned JSON Graph data

        :param paths: the Falcor paths of the batch
        :type paths: list
        :param kwargs: further arguments, unused
        :return: a JSON Graph response for the requested paths
        :rtype: dict
        """
        del kwargs
        self.batches.append(list(paths))
        if paths and paths[0][:1] == ['loco']:
            return {'loco': {'componentSummary': {'$type': 'atom', 'value': {'id': 'ROOT1'}}}}
        return CANNED_RESPONSE

    def perpetual_path_request(self, paths=None, **kwargs):
        """
        Record a path batch of a paginated request and answer with canned data

        :param paths: the Falcor paths of the batch
        :type paths: list
        :param kwargs: further arguments, unused
        :return: a JSON Graph response for the requested paths
        :rtype: dict
        """
        del kwargs
        self.batches.append(list(paths))
        return CANNED_RESPONSE


def _all_directory_path_batches():
    """
    Drive every DirectoryPathRequests method that assembles ART_PARTIAL_PATHS

    :return: every path batch the five artwork-consuming call sites send
    :rtype: list
    """
    session = _RecordingSession()
    builder = dir_path_requests.DirectoryPathRequests.__new__(dir_path_requests.DirectoryPathRequests)
    builder.nfsession = session
    builder.req_loco_list_root()
    builder.req_loco_list_genre('80057387')
    builder.req_seasons(VideoId(tvshowid='80057281'), 0)
    builder.req_episodes(VideoId(seasonid='80057283', tvshowid='80057281'))
    builder.req_lolomo_category('netflix.genres.cats')
    return session.batches


def test_art_partial_paths_is_empty():
    """
    ART_PARTIAL_PATHS stays defined but empty, so existing imports keep working

    The constant is the single remaining place where the retired artwork
    nodes could be requested, so an empty value proves they are gone.
    """
    assert isinstance(apipaths.ART_PARTIAL_PATHS, list)
    assert not apipaths.ART_PARTIAL_PATHS


def test_consumer_modules_hold_no_art_partial_paths_binding():
    """
    No consumer keeps ART_PARTIAL_PATHS in its own namespace

    Emptying the constant is worthless while a module holds its own binding: the
    name would still point at the old four-entry list and the batch would 404.
    """
    holders = [module_path for module_path in ART_PATH_CONSUMERS
               if hasattr(importlib.import_module(module_path), 'ART_PARTIAL_PATHS')]
    assert not holders, f'{holders} bind ART_PARTIAL_PATHS, which captures the list object at import time'


def test_consumer_modules_do_not_import_art_partial_paths_by_name():
    """No consumer imports ART_PARTIAL_PATHS by name, under any alias"""
    importers = {module_path: _art_partial_paths_importers(module_path)
                 for module_path in ART_PATH_CONSUMERS}
    offenders = {module_path: lines for module_path, lines in importers.items() if lines}
    assert not offenders, f'{offenders} import ART_PARTIAL_PATHS by name'


def test_no_retired_art_node_literal_survives_in_the_api_layer():
    """
    None of the retired node names is spelled as a literal in the API layer

    The scan covers every module that builds request paths, not just api_paths, so
    a literal reintroduced in a consumer is caught as well.
    """
    leftovers = {module_path: _retired_art_literals(module_path) for module_path in ART_PATH_SOURCES}
    offenders = {module_path: hits for module_path, hits in leftovers.items() if hits}
    assert not offenders, f'{offenders} still spell a retired artwork node'


def test_partial_path_sets_request_no_retired_art_node():
    """The api_paths partial-path sets resolve to no retired artwork node"""
    for partial_paths in ART_PATH_SETS:
        paths = apipaths.build_paths(['videos', 80057281], partial_paths)
        assert not _retired_art_nodes(paths), f'retired artwork node requested by {paths}'


def test_directory_path_request_batches_request_no_retired_art_node(globals_stub):
    """The five artwork-consuming directory batches resolve to no retired node"""
    del globals_stub
    for batch in _all_directory_path_batches():
        assert not _retired_art_nodes(batch), f'retired artwork node requested by {batch}'


def test_episodes_batch_keeps_only_the_title_delivery_path(globals_stub):
    """
    The episode batch still requests 'title'/'delivery' and nothing else of the show

    This is the one non-artwork path the emptied constant must not take with it.
    """
    del globals_stub
    builder_session = _RecordingSession()
    builder = dir_path_requests.DirectoryPathRequests.__new__(dir_path_requests.DirectoryPathRequests)
    builder.nfsession = builder_session
    builder.req_episodes(VideoId(seasonid='80057283', tvshowid='80057281'))
    show_paths = [path for path in builder_session.batches[0] if path[:2] == ['videos', '80057281']]
    assert show_paths == [['videos', '80057281', ['title', 'delivery']]]


def test_video_raw_data_requests_no_retired_art_node(globals_stub, monkeypatch):
    """The episode title path of get_video_raw_data resolves to no retired node"""
    del globals_stub
    batches = []

    def fake_make_call(func_name, data=None, endpoint=None):
        """
        Record the requested batch instead of calling the nfsession service

        :param func_name: the name of the requested nfsession method
        :type func_name: str
        :param data: the Falcor paths of the batch
        :type data: list
        :param endpoint: the IPC endpoint, unused
        :return: an empty response
        :rtype: dict
        """
        del func_name, endpoint
        batches.append(data)
        return {}

    monkeypatch.setattr(api_requests.common, 'make_call', fake_make_call)
    api_requests.get_video_raw_data(
        [VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281')])
    assert batches, 'no path batch was recorded'
    assert not _retired_art_nodes(batches[0]), f'retired artwork node requested by {batches[0]}'
    assert ['videos', 80057281, 'title'] in batches[0]


def test_get_videoid_info_requests_no_retired_art_node(globals_stub, monkeypatch):
    """The fallback batch of get_videoid_info resolves to no retired artwork node"""
    monkeypatch.setattr(globals_stub.LOCAL_DB, 'get_profile_config',
                        lambda key, default='': default, raising=False)
    calls = []

    def fake_get_info(*args, **kwargs):
        """
        Fail the cached lookup so the fallback path request is taken, then answer

        :param args: positional arguments given by the production code
        :type args: tuple
        :param kwargs: keyword arguments given by the production code
        :type kwargs: dict
        :return: the infolabel set of the video
        :rtype: list
        """
        del kwargs
        calls.append(args)
        if len(calls) == 1:
            raise TypeError('no infolabels are cached')
        return [{}, {}, {}]

    batches = []

    def fake_path_request(paths=None, **kwargs):
        """
        Record the requested batch and answer with an empty video node

        :param paths: the Falcor paths of the batch
        :type paths: list
        :param kwargs: further arguments, unused
        :return: a JSON Graph response holding an empty video node
        :rtype: dict
        """
        del kwargs
        batches.append(paths)
        return {'videos': {'80057282': {}}}

    monkeypatch.setattr(infolabels, 'get_info', fake_get_info)
    monkeypatch.setattr(infolabels, 'get_art', lambda *args, **kwargs: {})
    operations = nfsession_ops.NFSessionOperations.__new__(nfsession_ops.NFSessionOperations)
    monkeypatch.setattr(operations, 'path_request', fake_path_request)
    operations.get_videoid_info(VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281'))
    assert batches, 'no path batch was recorded'
    assert not _retired_art_nodes(batches[0]), f'retired artwork node requested by {batches[0]}'
    assert ['videos', 80057281, ['title', 'delivery']] in batches[0]


def test_title_path_survives_the_empty_constant():
    """The 'title' path added next to ART_PARTIAL_PATHS still resolves"""
    paths = apipaths.build_paths(['videos', 1], apipaths.ART_PARTIAL_PATHS + [['title']])
    assert paths == [['videos', 1, 'title']]


def test_delivery_path_survives_the_empty_constant():
    """The 'title'/'delivery' path added next to ART_PARTIAL_PATHS still resolves"""
    paths = apipaths.build_paths(['videos', 1], apipaths.ART_PARTIAL_PATHS + [[['title', 'delivery']]])
    assert paths == [['videos', 1, ['title', 'delivery']]]


def test_parse_art_falls_back_to_item_summary(globals_stub):
    """With no artwork nodes, poster comes from itemSummary.value.boxArt.url"""
    del globals_stub
    from resources.lib.kodi.infolabels import parse_art  # pylint: disable=import-outside-toplevel

    videoid = VideoId(movieid='80057281')
    item = {'itemSummary': {'$type': 'atom', 'value': {'boxArt': {'url': 'https://img/box.jpg'}}}}
    art = parse_art(videoid, item)
    assert art['poster'] == 'https://img/box.jpg'


def test_parse_art_without_item_summary_is_empty(globals_stub):
    """Missing itemSummary yields empty art values, not an exception"""
    del globals_stub
    from resources.lib.kodi.infolabels import parse_art  # pylint: disable=import-outside-toplevel

    videoid = VideoId(movieid='80057281')
    art = parse_art(videoid, {})
    assert art['poster'] == ''
    assert art['fanart'] == ''
    assert art['thumb'] == ''


def test_parse_art_for_episode_yields_empty_fallback_art(globals_stub):
    """
    An episode without artwork nodes yields empty values, not an exception

    Before the change this path passed four keyword arguments whose values
    came from ART_PARTIAL_PATHS; those are now absent.
    """
    del globals_stub
    from resources.lib.kodi.infolabels import parse_art  # pylint: disable=import-outside-toplevel

    videoid = VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281')
    art = parse_art(videoid, {})
    assert art == {'poster': '', 'fanart': '', 'thumb': '', 'landscape': '', 'clearlogo': ''}
