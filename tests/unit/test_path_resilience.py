# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Tests for the 404-tolerant path request
"""
# The tests exercise the private seam of SessionPathRequests on purpose: the resilience
# logic is not reachable through the public entry point without a full session.
# pylint: disable=protected-access
import copy
import json

import pytest

import resources.lib.common as common
from resources.lib.common.exceptions import HttpError404
from resources.lib.services.nfsession.session.path_blacklist import PATH_BLACKLIST
from resources.lib.services.nfsession.session.path_requests import SessionPathRequests


def _key(path):
    """Serialise a path the way the session layer does to key the blacklist"""
    return json.dumps(path, separators=(',', ':'))


@pytest.fixture(autouse=True)
def _reset_blacklist():
    """The blacklist is a module singleton; reset it around each test."""
    PATH_BLACKLIST.clear()
    yield
    PATH_BLACKLIST.clear()


class _FakeTransport:
    """Stands in for the HTTP layer: fails a whole batch if any of its
    paths is one the caller declared as failing."""

    def __init__(self, failing_paths):
        self.failing_paths = set(failing_paths)
        self.requested_batches = []

    def send(self, paths):
        self.requested_batches.append(list(paths))
        if any(self._is_failing(path) for path in paths):
            raise HttpError404
        return {'ok': {'$type': 'atom',
                       'value': [json.dumps(path, separators=(',', ':')) for path in paths]}}

    def _is_failing(self, path):
        return json.dumps(path, separators=(',', ':')) in self.failing_paths


def _make_resilient(failing_paths):
    """Build a SessionPathRequests whose _request_paths is backed by a fake transport."""
    transport = _FakeTransport(failing_paths)
    instance = SessionPathRequests.__new__(SessionPathRequests)
    instance._request_paths = transport.send
    return instance, transport


def test_single_failing_path_yields_empty_result():
    """A lone failing path yields an empty result, not an exception."""
    bad = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    instance, _ = _make_resilient({json.dumps(bad, separators=(',', ':'))})
    assert instance._path_request_resilient([bad]) == {}


def test_mixed_batch_keeps_surviving_paths():
    """A failing path is dropped; the surviving paths are still returned."""
    good = ['videos', 1, 'summary']
    bad = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    instance, _ = _make_resilient({json.dumps(bad, separators=(',', ':'))})
    result = instance._path_request_resilient([good, bad])
    assert result['ok']['value'] == ['["videos",1,"summary"]']


def test_two_failing_paths_both_dropped():
    """Halving isolates two failing paths in a two-element batch."""
    bad_a = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    bad_b = ['videos', 2, 'storyArt', '_665x375', 'jpg', 'value']
    failing = {json.dumps(bad_a, separators=(',', ':')), json.dumps(bad_b, separators=(',', ':'))}
    instance, _ = _make_resilient(failing)
    assert instance._path_request_resilient([bad_a, bad_b]) == {}


def test_untouched_batch_is_sent_unchanged():
    """A batch without failing paths is sent as one request, not split."""
    paths = [['videos', 1, 'summary'], ['videos', 1, 'title']]
    instance, transport = _make_resilient(set())
    instance._path_request_resilient(paths)
    assert transport.requested_batches == [paths]


class _MergeFakeTransport(_FakeTransport):
    """Fails a batch containing a failing path like _FakeTransport, but answers a
    surviving batch with the node registered for each of the paths it contains.

    The answer therefore depends on which paths a batch holds, which is what lets a
    halved batch end up with two non-empty halves that have to be merged.
    """

    def __init__(self, failing_keys, answers):
        super().__init__(failing_keys)
        self.answers = answers
        self.responses = []

    def send(self, paths):
        self.requested_batches.append(list(paths))
        if any(self._is_failing(path) for path in paths):
            raise HttpError404
        answer = {}
        for path in paths:
            # deepcopy: merge_dicts mutates nested dicts in place, and the
            # registered answers must survive the request unchanged
            common.merge_dicts(copy.deepcopy(self.answers[_key(path)]), answer)
        self.responses.append(answer)
        return answer


def _make_merging(failing_paths, answers):
    """Build a SessionPathRequests whose _request_paths answers per requested path."""
    transport = _MergeFakeTransport({_key(path) for path in failing_paths}, answers)
    instance = SessionPathRequests.__new__(SessionPathRequests)
    instance._request_paths = transport.send
    return instance, transport


def test_two_surviving_halves_are_merged():
    """A batch whose halves both answer is returned as a single merged jsonGraph.

    Every other resilience test either answers with an empty dict on one side (so the
    empty-side guards return early) or never splits at all, which leaves the merge of
    both halves unexecuted. Here each half splits again into one surviving and one
    failing path, so both halves come back non-empty and must be merged.
    """
    left_path = ['videos', 1, 'title']
    right_path = ['videos', 1, 'summary']
    bad_a = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    bad_b = ['videos', 2, 'storyArt', '_665x375', 'jpg', 'value']
    # both halves answer for the same node 'videos/1', so the merge has to recurse
    answers = {
        _key(left_path): {'videos': {'1': {'title': {'$type': 'atom', 'value': 'Show'}}}},
        _key(right_path): {'videos': {'1': {'summary': {'$type': 'atom', 'value': 'Text'}}}},
    }
    instance, transport = _make_merging([bad_a, bad_b], answers)

    merged = instance._path_request_resilient([left_path, bad_a, right_path, bad_b])

    # the whole batch fails once, then each half is split until only the failing
    # paths are alone in a request
    assert transport.requested_batches == [
        [left_path, bad_a, right_path, bad_b],
        [left_path, bad_a], [left_path], [bad_a],
        [right_path, bad_b], [right_path], [bad_b]]
    left_response = transport.responses[0]
    right_response = transport.responses[1]
    videos = merged['videos']['1']
    assert videos['title'] == {'$type': 'atom', 'value': 'Show'}
    assert videos['summary'] == {'$type': 'atom', 'value': 'Text'}
    # common.merge_dicts(dict_to_merge, merged_dict) merges into and returns its second
    # argument: the second half absorbs the first and is what the caller gets back,
    # the first half is left untouched. These two assertions pin that argument order.
    assert left_response == answers[_key(left_path)]
    assert merged == right_response


def test_blocked_path_is_not_requested_again():
    """The payoff of the blacklist: a rejected path costs one request, not one per call."""
    bad = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    instance, transport = _make_resilient({_key(bad)})

    assert instance.path_request([bad]) == {}
    # the rejected path is remembered under the serialised form path_request filters on
    assert PATH_BLACKLIST.is_blocked(_key(bad))
    assert transport.requested_batches == [[bad]]

    assert instance.path_request([bad]) == {}
    # the second call is answered by the blocked-path filter, without any request
    assert transport.requested_batches == [[bad]]


def test_blocked_path_is_filtered_out_of_a_larger_batch():
    """Only the blocked path is dropped, the surviving paths are still requested."""
    good = ['videos', 1, 'summary']
    bad = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    PATH_BLACKLIST.block(_key(bad))
    instance, transport = _make_resilient(set())

    result = instance.path_request([good, bad])

    assert transport.requested_batches == [[good]]
    assert result['ok']['value'] == [_key(good)]


def test_request_of_only_blocked_paths_issues_no_request():
    """A batch that is blocked entirely is answered with an empty jsonGraph, not sent."""
    bad_a = ['videos', 1, 'boxarts', ['_665x375'], 'jpg', 'value']
    bad_b = ['videos', 2, 'storyArt', '_665x375', 'jpg', 'value']
    PATH_BLACKLIST.block(_key(bad_a))
    PATH_BLACKLIST.block(_key(bad_b))
    instance, transport = _make_resilient(set())

    assert instance.path_request([bad_a, bad_b]) == {}
    assert not transport.requested_batches
