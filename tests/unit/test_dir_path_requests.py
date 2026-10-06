# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Tests for the directory builder path requests
"""
from resources.lib.services.nfsession.directorybuilder import dir_path_requests
from resources.lib.utils.data_types import LoCo


class _RecordingSession:
    """Records every path batch and returns canned responses"""

    def __init__(self, loco_id):
        self.loco_id = loco_id
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
            return {'loco': {'componentSummary': {'$type': 'atom', 'value': {'id': self.loco_id}}}}
        return {'locos': {self.loco_id: {
            'componentSummary': {'$type': 'atom', 'value': {'length': 0}},
        }}}


class _NoIdSession(_RecordingSession):
    """Answers every request with a response that has no LoCo root id"""

    def path_request(self, paths=None, **kwargs):
        """
        Record a path batch and answer without any root id

        :param paths: the Falcor paths of the batch
        :type paths: list
        :param kwargs: further arguments, unused
        :return: a JSON Graph response lacking the root id
        :rtype: dict
        """
        del kwargs
        self.batches.append(list(paths))
        return {'loco': {'componentSummary': {'$type': 'atom', 'value': {'length': 0}}}}


def _build_builder(session):
    """
    Create a DirectoryPathRequests instance with a fake session

    The instance is created without running __init__, because only the session
    attribute is needed to exercise the unbound production method.

    :param session: the fake nfsession to be used by the builder
    :type session: _RecordingSession
    :return: a directory path requests instance bound to the fake session
    :rtype: resources.lib.services.nfsession.directorybuilder.dir_path_requests.DirectoryPathRequests
    """
    builder = dir_path_requests.DirectoryPathRequests.__new__(dir_path_requests.DirectoryPathRequests)
    builder.nfsession = session
    return builder


def test_loco_root_uses_singular_form_first(globals_stub):
    """The first request uses the singular 'loco' form to obtain the root id"""
    del globals_stub
    session = _RecordingSession('ROOT1')
    _build_builder(session).req_loco_list_root()
    assert session.batches[0] == [['loco', 'componentSummary']]


def test_loco_root_second_request_uses_locos_with_root_id(globals_stub):
    """The follow-up request uses the plural 'locos' keyed by the root id"""
    del globals_stub
    session = _RecordingSession('ROOT1')
    _build_builder(session).req_loco_list_root()
    assert len(session.batches) == 2
    assert all(path[:2] == ['locos', 'ROOT1'] for path in session.batches[1])


def test_loco_root_keeps_range_dicts_at_top_level(globals_stub):
    """Every range dict of the follow-up request sits at the top level of its path"""
    del globals_stub
    session = _RecordingSession('ROOT1')
    _build_builder(session).req_loco_list_root()
    for path in session.batches[1]:
        ranges = [element for element in path if isinstance(element, dict)]
        assert ranges, f'no range dict found in {path}'
        assert 'from' in ranges[0] or 'to' in ranges[0], f'nested range dict in {path}'


def test_loco_root_returns_loco_with_lists(globals_stub):
    """The follow-up response is returned as a LoCo instance rooted at the fetched id"""
    del globals_stub
    session = _RecordingSession('ROOT1')
    result = _build_builder(session).req_loco_list_root()
    assert isinstance(result, LoCo)
    assert result.id == 'ROOT1'


def test_loco_root_handles_missing_root_id(globals_stub):
    """A response without a root id yields an empty LoCo, not a crash"""
    del globals_stub
    session = _NoIdSession('ROOT1')
    result = _build_builder(session).req_loco_list_root()
    assert isinstance(result, LoCo)
    assert result.id == 'EMPTY'
    assert isinstance(result.lists, dict)
    assert not result.lists
    assert session.batches == [[['loco', 'componentSummary']]]
