# -*- coding: utf-8 -*-
"""Tests for wiring the GraphQL client into the session hierarchy."""
import pytest

from resources.lib.common import VideoId
from resources.lib.common.exceptions import (GraphQLAuthError, GraphQLProtocolError,
                                             GraphQLRequestError)
from resources.lib.services.nfsession import nfsession_ops
from resources.lib.services.nfsession.graphql import artwork
from resources.lib.services.nfsession.session.path_requests import SessionPathRequests


def test_path_requests_exposes_graphql_request():
    """SessionPathRequests must reach the client without a second wiring path.

    Both halves are asserted on the real class, not on a class the test builds
    itself: a self-built composition would keep passing if the module shipped
    without it. graphql_request posts through post_safe, which only
    SessionAccess defines, so a composition that dropped the access half would
    satisfy the first assertion alone and fail at the first real request.
    """
    assert hasattr(SessionPathRequests, 'graphql_request')
    assert hasattr(SessionPathRequests, 'post_safe')


SUPPLEMENTAL_ID = '39c9a88a-a56e-4c8a-921c-3c1f86c0ebb9_62682962X28X6548X1551537755876'
"""The shape videoid.py:47 documents for a SUPPLEMENTAL row, evidence id and nothing else."""


def _make_ops(response=None, error=None):
    ops = nfsession_ops.NFSessionOperations.__new__(nfsession_ops.NFSessionOperations)
    ops.calls = []

    def graphql_request(operation_name, variables=None):
        ops.calls.append((operation_name, variables))
        if error:
            raise error
        return response or {}

    ops.graphql_request = graphql_request
    return ops


def _image(key, url, width=665, height=375):
    return {'__typename': 'Image', 'key': key, 'url': url,
            'width': width, 'height': height,
            'available': True, 'status': 'RESOLVED'}


def _entity(video_id, **nodes):
    return {'__typename': 'Movie', 'videoId': video_id, 'art': nodes}


def test_get_video_art_queries_detail_modal_for_the_video():
    """The operation name and the id shape are the ones the live probe validated."""
    ops = _make_ops(response={'playbackEntities': [], 'unifiedEntities': []})
    ops.get_video_art(VideoId(movieid='80057281'))
    name, variables = ops.calls[0]
    assert name == 'DetailModal'
    assert variables['videoId'] == 80057281
    assert isinstance(variables['videoId'], int)
    assert variables['unifiedEntityId'] == 'Video:80057281'


def test_get_video_art_returns_the_mapped_art():
    image = _image('StoryArt|a|b|en', 'fanart.jpg', width=848, height=477)
    ops = _make_ops(response={'playbackEntities': [_entity(80057281, art=image)]})
    art = ops.get_video_art(VideoId(movieid='80057281'))
    assert art['fanart'] == 'fanart.jpg'


def test_get_video_art_does_not_book_a_foreign_entitys_artwork():
    """The id reaches the extractor, so a promo's wider image is not booked.

    The request enables hasPromoVideoOverride and videoMerchEnabled, and those
    entries carry their own videoId. This is the wiring-level view of the same
    rule the artwork tests pin directly: get_video_art must pass the requested
    id down, not the response as a whole.
    """
    response = {'playbackEntities': [
        _entity(80057281, art=_image('StoryArt|a|b|en', 'title.jpg', width=848, height=477)),
        _entity(90000001, art=_image('StoryArt|c|d|en', 'promo.jpg', width=1920, height=1080))]}
    ops = _make_ops(response=response)
    assert ops.get_video_art(VideoId(movieid='80057281'))['fanart'] == 'title.jpg'


def test_get_video_art_returns_empty_art_when_the_request_fails():
    """A failing lookup degrades to empty art rather than raising into the UI."""
    ops = _make_ops(error=GraphQLRequestError('boom'))
    art = ops.get_video_art(VideoId(movieid='80057281'))
    assert art == artwork.EMPTY_ART


def test_get_video_art_returns_empty_art_on_a_protocol_failure():
    """A protocol failure degrades like a transport failure, on purpose.

    A retired persisted query, a non-auth 'errors' body and an HTML or WAF
    page all end in a title without a picture. None of them is something the
    caller can act on, so letting the error escape would only break a listing
    that would otherwise render.
    """
    ops = _make_ops(error=GraphQLProtocolError('GraphQL returned errors for DetailModal'))
    art = ops.get_video_art(VideoId(movieid='80057281'))
    assert art == artwork.EMPTY_ART


def test_empty_art_is_the_shared_key_set():
    """The failure result and the success result must carry the same keys.

    parse_art() splats the art dict and reads only the keys it knows, so a
    field added to one of the two shapes and not the other would disappear
    with no error and no picture. This pins both shapes to EMPTY_ART.
    """
    ops = _make_ops(response={'unifiedEntities': [{
        'unifiedEntityId': 'Video:80057281',
        'art': {'logo': _image('LOGO_BRANDED_HORIZONTAL|a|b|de', 'logo.jpg',
                               width=1000, height=250)}}]})
    extracted = ops.get_video_art(VideoId(movieid='80057281'))
    assert extracted == {'thumb': '', 'landscape': '', 'fanart': '', 'clearlogo': 'logo.jpg'}
    assert set(extracted) == set(artwork.EMPTY_ART)
    # The failure path hands out a copy: the shared mapping must stay pristine.
    assert _make_ops(error=GraphQLRequestError('boom')).get_video_art(
        VideoId(movieid='80057281')) is not artwork.EMPTY_ART


def test_get_video_art_reraises_auth_errors():
    """An expired session must surface, not be silently turned into missing art.

    The session failure has to reach the caller so the refresh path can run.
    """
    ops = _make_ops(error=GraphQLAuthError('expired'))
    with pytest.raises(GraphQLAuthError):
        ops.get_video_art(VideoId(movieid='80057281'))


def test_get_video_art_degrades_on_a_non_numeric_video_id():
    """A SUPPLEMENTAL row has no video id to ask for, and must not raise.

    dir_builder_items builds these rows for trailers and the like, and they
    reach get_art like any other row. int() on the evidence id raises
    ValueError, which used to escape the one method whose contract is that
    every failure degrades to empty art.
    """
    videoid = VideoId(supplementalid=SUPPLEMENTAL_ID)
    assert videoid.mediatype == VideoId.SUPPLEMENTAL
    ops = _make_ops(response={'playbackEntities': []})
    assert ops.get_video_art(videoid) == artwork.EMPTY_ART
    assert not ops.calls, 'a non-numeric id must not reach the network'
