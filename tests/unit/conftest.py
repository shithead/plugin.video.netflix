# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Pytest fixtures for the unit test suite

    The Kodi stubs are installed at module level, before any `resources.lib` module
    is imported, because several stubbed names are needed while those modules are
    loaded.
"""
import pytest

from tests.unit import kodi_stubs

kodi_stubs.install()

# The imports below must stay behind kodi_stubs.install(), because importing
# `resources.lib` loads the stubbed Kodi names.
# pylint: disable=wrong-import-position
from resources.lib.common.exceptions import CacheMiss  # noqa: E402
from resources.lib.globals import G  # noqa: E402


class _FakeAddon:
    """Stand-in for xbmcaddon.Addon"""

    def getSetting(self, name):  # pylint: disable=invalid-name
        """
        Return the value of a setting

        :param name: name of the setting
        :type name: str
        :return: an empty setting
        :rtype: str
        """
        del name
        return ''

    def getSettingInt(self, name):  # pylint: disable=invalid-name
        """
        Return the integer value of a setting

        :param name: name of the setting
        :type name: str
        :return: a zero setting
        :rtype: int
        """
        del name
        return 0

    def getSettingBool(self, name):  # pylint: disable=invalid-name
        """
        Return the boolean value of a setting

        :param name: name of the setting
        :type name: str
        :return: a false setting
        :rtype: bool
        """
        del name
        return False

    def getLocalizedString(self, msgctxt):  # pylint: disable=invalid-name
        """
        Return the localized string of a message id

        :param msgctxt: id of the message
        :type msgctxt: int
        :return: the message id as its own translation
        :rtype: str
        """
        return str(msgctxt)

    def getAddonInfo(self, name):  # pylint: disable=invalid-name
        """
        Return the metadata of the add-on

        :param name: name of the metadata entry
        :type name: str
        :return: the metadata of the add-on
        :rtype: dict
        """
        del name
        return {'id': 'plugin.video.netflix', 'name': 'Netflix', 'version': '1.23.5'}

    def setSetting(self, name, value):  # pylint: disable=invalid-name
        """
        Store the value of a setting

        :param name: name of the setting
        :type name: str
        :param value: value of the setting
        :type value: str
        """
        del name, value


class _FakeLocalDb:
    """Stand-in for the profile database"""

    def get_active_profile_guid(self):
        """
        Return the guid of the active profile

        :return: a fixed profile guid
        :rtype: str
        """
        return 'ABCDEF'

    def get_value(self, key, table=None):
        """
        Return the value of a database entry

        :param key: name of the entry
        :type key: str
        :param table: name of the table the entry is stored in
        :type table: str
        :return: an empty value
        :rtype: str
        """
        del key, table
        return ''

    def get_guid_owner_profile(self):
        """
        Return the guid of the profile the current one belongs to

        :return: a fixed owner profile guid
        :rtype: str
        """
        return 'ABCDEF'


class _FakeSharedDb:
    """Stand-in for the shared database"""

    def get_value(self, key, default=None):
        """
        Return the value of a database entry

        :param key: name of the entry
        :type key: str
        :param default: value returned for an unknown entry
        :type default: str
        :return: the default value
        :rtype: str
        """
        del key
        return default


class _FakeCache:
    """
    Stand-in for resources.lib.common.cache.Cache

    The real Cache talks to the add-on service over IPC. Tests need an in-memory
    replacement that raises CacheMiss on an unknown identifier, which is what
    get_art() relies on to bypass the cache.
    """

    def __init__(self):
        """Create an empty cache store"""
        self.store = {}

    def get(self, bucket, identifier):
        """
        Return the cached data of an entry

        :param bucket: the cache bucket of the entry
        :type bucket: dict
        :param identifier: the identifier of the entry
        :type identifier: str
        :return: the cached data
        :rtype: any
        :raises CacheMiss: if the entry is not cached
        """
        key = (bucket['name'], identifier)
        if key not in self.store:
            raise CacheMiss
        return self.store[key]

    def add(self, bucket, identifier, data, ttl=None, expires=None, delayed_db_op=False):
        """
        Cache the data of an entry

        :param bucket: the cache bucket of the entry
        :type bucket: dict
        :param identifier: the identifier of the entry
        :type identifier: str
        :param data: the data to cache
        :type data: any
        :param ttl: time to live of the entry
        :type ttl: int
        :param expires: expiration time of the entry
        :type expires: datetime.datetime
        :param delayed_db_op: whether the database write is delayed
        :type delayed_db_op: bool
        """
        del ttl, expires, delayed_db_op
        self.store[(bucket['name'], identifier)] = data

    def delete(self, bucket, identifier, including_suffixes=False):
        """
        Remove a cached entry

        :param bucket: the cache bucket of the entry
        :type bucket: dict
        :param identifier: the identifier of the entry
        :type identifier: str
        :param including_suffixes: whether suffixed entries are removed too
        :type including_suffixes: bool
        """
        del including_suffixes
        self.store.pop((bucket['name'], identifier), None)

    def clear(self, buckets=None, clear_database=True):
        """
        Clear the cache

        :param buckets: list of buckets to clear, if not specified clear all the cache
        :type buckets: list
        :param clear_database: if True clear also the database data
        :type clear_database: bool
        """
        del clear_database
        if buckets is None:
            self.store.clear()
            return
        names = {bucket['name'] for bucket in buckets}
        for key in [key for key in self.store if key[0] in names]:
            del self.store[key]


@pytest.fixture(name='globals_stub')
def fixture_globals_stub(monkeypatch):
    """
    Provide a G object populated enough for the API-layer tests

    G is a module singleton, so its attributes are set in place. They are set
    through monkeypatch, which restores the original values after the test, so
    that nothing leaks into the following tests. `raising=False` is needed because
    most of them are only created by `resources.lib.run_addon`, not at import time.

    :return: the globals object of the add-on
    :rtype: resources.lib.globals.GlobalVariables
    """
    monkeypatch.setattr(G, 'ADDON', _FakeAddon(), raising=False)
    monkeypatch.setattr(G, 'CACHE', _FakeCache(), raising=False)
    monkeypatch.setattr(G, 'LOCAL_DB', _FakeLocalDb(), raising=False)
    monkeypatch.setattr(G, 'SHARED_DB', _FakeSharedDb(), raising=False)
    monkeypatch.setattr(G, 'ORIGIN_PROFILE_GUID', 'ABCDEF', raising=False)
    monkeypatch.setattr(G, 'PLUGIN_HANDLE', -1, raising=False)
    return G
