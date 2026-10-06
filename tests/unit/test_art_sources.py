# -*- coding: utf-8 -*-
"""Tests for combining the Falcor and GraphQL art sources."""
from resources.lib.common import VideoId
from resources.lib.kodi import infolabels


GRAPHQL_ART = {'thumb': 'g-thumb.jpg', 'landscape': 'g-thumb.jpg',
               'fanart': 'g-fanart.jpg', 'clearlogo': 'g-logo.jpg'}


def test_graphql_art_fills_every_field():
    """With a GraphQL result and no Falcor data, every field comes from GraphQL."""
    videoid = VideoId(movieid='80057281')
    art = infolabels.parse_art(videoid, {}, graphql_art=GRAPHQL_ART)
    assert art['poster'] == ''
    assert art['thumb'] == 'g-thumb.jpg'
    assert art['landscape'] == 'g-thumb.jpg'
    assert art['fanart'] == 'g-fanart.jpg'
    assert art['clearlogo'] == 'g-logo.jpg'


def test_falcor_fallback_is_kept():
    """The itemSummary boxArt path must still work on its own."""
    videoid = VideoId(movieid='80057281')
    item = {'itemSummary': {'$type': 'atom', 'value': {'boxArt': {'url': 'falcor.jpg'}}}}
    art = infolabels.parse_art(videoid, item)
    assert art['poster'] == 'falcor.jpg'


def test_graphql_thumb_outranks_the_falcor_landscape_fallback():
    """A 665x375 GraphQL image beats the 342x192 Falcor card for thumb."""
    videoid = VideoId(movieid='80057281')
    item = {'itemSummary': {'$type': 'atom', 'value': {'boxArt': {'url': 'falcor.jpg'}}}}
    art = infolabels.parse_art(videoid, item, graphql_art=GRAPHQL_ART)
    assert art['thumb'] == 'g-thumb.jpg'
    assert art['poster'] == 'falcor.jpg'


def test_missing_graphql_art_falls_back_entirely_to_falcor():
    """An empty GraphQL result must not blank the Falcor poster."""
    videoid = VideoId(movieid='80057281')
    item = {'itemSummary': {'$type': 'atom', 'value': {'boxArt': {'url': 'falcor.jpg'}}}}
    art = infolabels.parse_art(videoid, item,
                               graphql_art={'thumb': '', 'landscape': '',
                                            'fanart': '', 'clearlogo': ''})
    assert art['poster'] == 'falcor.jpg'


def test_landscape_falls_back_to_the_graphql_thumb():
    """GraphQL sent no landscape, so the thumbnail carries both slots.

    Otherwise entries in one series would show an edge image for some titles
    and not for others.
    """
    videoid = VideoId(movieid='80057281')
    art = infolabels.parse_art(videoid, {}, graphql_art={**GRAPHQL_ART, 'landscape': ''})
    assert art['landscape'] == 'g-thumb.jpg'


def test_neither_source_yields_empty_art_without_raising():
    videoid = VideoId(movieid='80057281')
    art = infolabels.parse_art(videoid, {})
    assert art['poster'] == ''
    assert art['fanart'] == ''


def test_unspecified_videotype_gets_no_clearlogo():
    """An UNSPECIFIED videotype gets no clearlogo key at all, logo supplied or not.

    _assign_art() sets that key only for a concrete videotype, so the GraphQL
    logo must not smuggle it into the art of a bare videoid.
    """
    art = infolabels.parse_art(VideoId(videoid='80057281'), {}, graphql_art=GRAPHQL_ART)
    assert 'clearlogo' not in art


def test_both_sources_absent_for_an_episode():
    """Episodes take interestingMoment for thumb; absent here, it must not raise."""
    videoid = VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281')
    art = infolabels.parse_art(videoid, {}, graphql_art=GRAPHQL_ART)
    assert art['thumb'] == 'g-thumb.jpg'


# The two tests below call _assign_art directly. parse_art() supplies only the
# 'fallback' card, so through it the Falcor thumb chain is unreachable and its
# precedence over - or subordination to - the GraphQL image cannot be observed.


def test_graphql_thumb_outranks_the_falcor_thumb_chain():
    """Both sources populated: the GraphQL image wins thumb and landscape."""
    videoid = VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281')
    art = infolabels._assign_art(videoid,  # pylint: disable=protected-access
                                 interesting_moment='falcor-thumb.jpg',
                                 boxart_large='falcor-large.jpg',
                                 boxart_small='falcor-small.jpg',
                                 thumb='g-thumb.jpg',
                                 landscape='g-landscape.jpg')
    assert art['thumb'] == 'g-thumb.jpg'
    assert art['landscape'] == 'g-landscape.jpg'


def test_falcor_thumb_chain_still_serves_the_videotypes_that_use_it():
    """Without GraphQL art, an episode takes interestingMoment and a movie the boxart.

    The mediatype guard decides this and nothing else does, so it is pinned
    here. 'landscape' follows 'thumb' in both cases.
    """
    falcor_art = {'interesting_moment': 'falcor-thumb.jpg', 'boxart_large': 'falcor-large.jpg'}
    episode = infolabels._assign_art(  # pylint: disable=protected-access
        VideoId(episodeid='80057282', seasonid='80057283', tvshowid='80057281'), **falcor_art)
    movie = infolabels._assign_art(VideoId(movieid='80057281'), **falcor_art)  # pylint: disable=protected-access
    assert episode['thumb'] == 'falcor-thumb.jpg'
    assert movie['thumb'] == 'falcor-large.jpg'
    assert episode['landscape'] == episode['thumb']
    assert movie['landscape'] == movie['thumb']
