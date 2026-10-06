# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Tests for the fields and query parameters retired from the request sets
"""
import resources.lib.utils.api_paths as apipaths


# Only these two are retired. Upstream PR #1796 also drops 'dpSupplementalMessage',
# 'sequiturEvidence' and 'promoVideo', but the plugin reads all three
# (infolabels.py:94, infolabels.py:109, INFO_MAPPINGS in api_paths.py:115 and
# dir_builder_utils.py:59), so they stay. 'regularSynopsis' stays too: INFO_MAPPINGS
# only has it commented out (api_paths.py:101), and its removal is not part of this step.
REMOVED_FIELDS = (
    'requestId',
    'evidence',
)

RETIRED_PARAMS = (
    'routeAPIRequestsThroughFTL',
    'isVolatileBillboardsEnabled',
    'isTop10Supported',
)

KEPT_FIELDS = (
    'dpSupplementalMessage',
    'sequiturEvidence',
    'promoVideo',
    'regularSynopsis',
)


def _requested_field_names(partial_paths):
    """
    Flatten every atomic field name out of a partial-path set

    :param partial_paths: a partial-path set from the api_paths module
    :type partial_paths: list
    :return: the set of requested field names
    :rtype: set
    """
    names = set()
    for entry in partial_paths:
        for item in (entry if isinstance(entry, list) else [entry]):
            if isinstance(item, list) and all(isinstance(part, str) for part in item):
                names.update(item)
    return names


def test_video_list_paths_drop_retired_fields():
    """VIDEO_LIST_PARTIAL_PATHS requests no retired field"""
    requested = _requested_field_names(apipaths.VIDEO_LIST_PARTIAL_PATHS)
    for field in REMOVED_FIELDS:
        assert field not in requested


def test_episodes_paths_drop_retired_fields():
    """EPISODES_PARTIAL_PATHS requests no retired field"""
    requested = _requested_field_names(apipaths.EPISODES_PARTIAL_PATHS)
    for field in REMOVED_FIELDS:
        assert field not in requested


def test_video_list_paths_keep_consumed_fields():
    """VIDEO_LIST_PARTIAL_PATHS keeps the fields the add-on reads"""
    requested = _requested_field_names(apipaths.VIDEO_LIST_PARTIAL_PATHS)
    for field in KEPT_FIELDS:
        assert field in requested


def test_basic_video_list_paths_are_untouched():
    """VIDEO_LIST_BASIC_PARTIAL_PATHS is not part of this step"""
    assert apipaths.VIDEO_LIST_BASIC_PARTIAL_PATHS == [
        [['title', 'queue', 'watched', 'summary', 'type', 'id']]
    ]


def test_event_paths_are_untouched():
    """EVENT_PATHS keeps requestId, which am_video_events.py:196 reads"""
    assert apipaths.EVENT_PATHS == [
        [['requestId', 'title', 'runtime', 'queue', 'bookmarkPosition', 'watched', 'trackIds']]
    ]


def test_default_request_params_drop_retired_entries(globals_stub):  # pylint: disable=unused-argument
    """The default query parameters contain no retired entry"""
    from resources.lib.services.nfsession.session.http_requests import (  # pylint: disable=import-outside-toplevel
        SessionHTTPRequests)

    endpoint_conf = {'address': '/pathEvaluator', 'is_api_call': True,
                     'use_default_params': True, 'add_auth_url': None,
                     'content_type': 'application/x-www-form-urlencoded'}
    instance = SessionHTTPRequests.__new__(SessionHTTPRequests)
    _, headers, params = instance._prepare_request_properties(endpoint_conf, {})  # pylint: disable=protected-access
    assert headers
    for retired in RETIRED_PARAMS:
        assert retired not in params
    for kept in ('drmSystem', 'falcor_server', 'withSize', 'materialize'):
        assert kept in params
    assert params['original_path'] == '/shakti/mre/pathEvaluator'
