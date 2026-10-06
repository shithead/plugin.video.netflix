# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Tests for the path blacklist
"""
import resources.lib.services.nfsession.session.path_blacklist as pbl


def test_is_blocked_is_false_for_unknown_path():
    assert not pbl.PATH_BLACKLIST.is_blocked('["videos",1,"title"]')


def test_block_then_is_blocked():
    blacklist = pbl.PathBlacklist()
    assert not blacklist.is_blocked('["a"]')
    blacklist.block('["a"]')
    assert blacklist.is_blocked('["a"]')
    assert blacklist.blocked_count() == 1


def test_merge_blocks_top_level_errored_path():
    """A node answered with $error blocks its own key path."""
    blacklist = pbl.PathBlacklist()
    response = {'locos': {'$error': 'Invalid path', 'path': 'locos'}}
    blacklist.merge(response)
    assert blacklist.is_blocked('locos')
    assert blacklist.blocked_count() == 1


def test_merge_blocks_nested_errored_path():
    """A nested $error blocks the full key chain up to it."""
    blacklist = pbl.PathBlacklist()
    response = {'videos': {'1': {'title': {'$error': 'Invalid path'}}}}
    blacklist.merge(response)
    assert blacklist.is_blocked('videos/1/title')
    assert blacklist.blocked_count() == 1


def test_merge_ignores_healthy_response():
    """A response without any $error blocks nothing."""
    blacklist = pbl.PathBlacklist()
    response = {'videos': {'1': {'title': {'$type': 'atom', 'value': 'Show'}}}}
    blacklist.merge(response)
    assert blacklist.blocked_count() == 0


def test_merge_on_empty_response():
    """An empty response blocks nothing."""
    blacklist = pbl.PathBlacklist()
    blacklist.merge({})
    assert blacklist.blocked_count() == 0


def test_merge_does_not_add_type_keys_to_the_chain():
    """Keys starting with $ are metadata, never part of the blocked chain.

    The '$error' deliberately sits below a '$' prefixed key: that is the only shape on
    which the startswith('$') guard in _scan is load bearing. With the guard removed,
    the '$error' below '$ref' would be reached and 'videos/$ref' would be blocked.
    """
    blacklist = pbl.PathBlacklist()
    response = {'videos': {'$type': 'ref', '$ref': {'$error': 'Invalid path'}}}
    blacklist.merge(response)
    assert blacklist.blocked_count() == 0
    assert not blacklist.is_blocked('videos/$ref')
    assert not blacklist.is_blocked('videos')


def test_clear_removes_every_blocked_key():
    blacklist = pbl.PathBlacklist()
    blacklist.block('["a"]')
    blacklist.clear()
    assert blacklist.blocked_count() == 0
    assert not blacklist.is_blocked('["a"]')
