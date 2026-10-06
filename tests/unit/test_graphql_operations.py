# -*- coding: utf-8 -*-
"""Tests for the GraphQL persisted-query catalogue and its error taxonomy."""
import uuid

import pytest

from resources.lib.common import exceptions
from resources.lib.services.nfsession.graphql import operations


def test_every_operation_has_a_persisted_query_id():
    """Every catalogue entry maps an operation name to a UUID."""
    assert len(operations.OPERATIONS) == 21
    for name, query_id in operations.OPERATIONS.items():
        assert query_id, f'{name} has an empty persistedQuery.id'
        try:
            uuid.UUID(query_id)
        except (AttributeError, TypeError, ValueError):
            pytest.fail(f'{name} id is not a UUID: {query_id}')


def test_detail_modal_is_present_with_the_probed_id():
    """DetailModal is the operation the live probe validated."""
    assert operations.OPERATIONS['DetailModal'] == 'e5748389-c3b9-496e-bcea-64883cff1e87'


def test_persisted_version_is_102():
    """All 601 recorded requests across seven captures carried version 102."""
    assert operations.PERSISTED_VERSION == 102


def test_every_default_entry_has_a_catalogue_entry():
    """A default for an unknown operation would send an incomplete query identity."""
    assert set(operations.DEFAULT_VARIABLES) <= set(operations.OPERATIONS)


def test_operations_without_defaults_are_not_yet_implemented():
    """Names the exact gap, so adding an operation without defaults fails here.

    Defaults arrive with the task that needs them; the catalogue is broader
    by design.
    """
    without_defaults = {'CLCSInterstitialAccountPages', 'CLCSInterstitialLolomo',
                        'CLCSInterstitialPlaybackAndPostPlayback', 'CLCSInterstitialProfileGate',
                        'CarouselPage', 'DetailModalTrailers', 'FetchMoreSections',
                        'GetBrowsePage', 'GetGenreSubgenres', 'LinearChannelCheck',
                        'MiniModalQuery', 'PreviewModalEpisodeSelector',
                        'PreviewModalEpisodeSelectorSeasonEpisodes',
                        'PreviewModalUnifiedEntity', 'PreviewModalVideoTitleGroup',
                        'SearchPageQueryResults', 'SetEntityThumbRating', 'UpdatePage',
                        'VideoDetailsModalSimilars'}
    assert set(operations.OPERATIONS) - set(operations.DEFAULT_VARIABLES) == without_defaults


def test_detail_modal_defaults_match_the_probed_body():
    """The defaults are the fields the working probe sent, verbatim in name and type."""
    defaults = operations.DEFAULT_VARIABLES['DetailModal']
    assert defaults['opaqueImageFormat'] == 'JPG'
    assert defaults['transparentImageFormat'] == 'PNG'
    assert defaults['videoMerchContext'] == 'BROWSE'
    assert defaults['textEvidenceUiContext'] == 'ODP'
    assert defaults['videoMerchEnabled'] is True
    assert defaults['fetchPromoVideoOverride'] is False
    assert defaults['hasPromoVideoOverride'] is True
    assert defaults['promoVideoId'] == 0
    assert defaults['isLiveEpisodic'] is False
    assert defaults['includeCroppedLogo'] is False
    assert defaults['checkLinearChannel'] is True
    # Callers supply these two per request; they must not be defaulted.
    assert 'videoId' not in defaults
    assert 'unifiedEntityId' not in defaults


def test_error_taxonomy_is_three_distinct_classes():
    """Auth failures must not be catchable as transport failures.

    A subclass relation here would let `except GraphQLRequestError` swallow
    an expired session and return empty art instead of refreshing. The reverse
    relation is just as damaging and just as invisible: `except
    GraphQLAuthError` in get_video_art would swallow every transport failure
    and re-raise it, so a timeout on one title would be reported as an expired
    session. Both directions are therefore closed by the same assertion -
    each class must derive from Exception and from nothing else.
    """
    classes = (exceptions.GraphQLRequestError, exceptions.GraphQLAuthError,
               exceptions.GraphQLProtocolError)
    assert len(set(classes)) == 3
    assert all(cls.__bases__ == (Exception,) for cls in classes), (
        'the three GraphQL errors must be siblings: any parent relation lets '
        'one except clause swallow another class')


def test_catalogue_covers_the_operations_the_plan_depends_on():
    """Pin the operations later tasks call by name."""
    for required in ('DetailModal', 'useProfilesSummaryQuery'):
        assert required in operations.OPERATIONS
