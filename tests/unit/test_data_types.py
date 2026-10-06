# -*- coding: utf-8 -*-
"""Tests for the LoCo data helpers."""
from resources.lib.utils.data_types import _filterout_loco_contexts


def test_filterout_removes_lists_of_blacklisted_context():
    """Lists whose context matches are removed from data['lists']."""
    data = {
        'locos': {'ROOT': {'componentSummary': {'value': {'length': 2}}}},
        'lists': {
            'BILL': {'componentSummary': {'value': {'context': 'billboard'}}},
            'ROW': {'componentSummary': {'value': {'context': 'row'}}},
        },
    }
    _filterout_loco_contexts(data, ['billboard'])
    assert set(data['lists']) == {'ROW'}


def test_filterout_tolerates_missing_lists_key():
    """A partial response without 'lists' does not raise.

    This is the case a halved batch produces: the surviving half of the
    response may carry no 'lists' key at all.
    """
    data = {'locos': {'ROOT': {}}}
    _filterout_loco_contexts(data, ['billboard'])
    assert data == {'locos': {'ROOT': {}}}


def test_filterout_tolerates_lists_without_component_summary():
    """A list entry without componentSummary is kept, not deleted."""
    data = {'lists': {'X': {}}}
    _filterout_loco_contexts(data, ['billboard'])
    assert set(data['lists']) == {'X'}


def test_filterout_on_empty_data():
    """Empty data is a no-op."""
    _filterout_loco_contexts({}, ['billboard'])
