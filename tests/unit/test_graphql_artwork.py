# -*- coding: utf-8 -*-
"""Tests for mapping GraphQL Image nodes onto Kodi art fields.

Every document that feeds extract_art() is built through _requested() or
_foreign(), so each one states which entity owns which Image node. A document
that put all of its nodes in one anonymous entity would pass under both a
document-wide walk and an entity-scoped one, which is exactly why such
documents are not used here.
"""
from resources.lib.services.nfsession.graphql import artwork


REQUESTED = 80057281
FOREIGN = 70000001

NO_ART = {'thumb': '', 'landscape': '', 'fanart': '', 'clearlogo': ''}
"""Spelled out here rather than imported, so a change to EMPTY_ART cannot silently pass."""


def _image(key, url='https://img/x.jpg', width=665, height=375, available=True, status='RESOLVED'):
    return {'__typename': 'Image', 'key': key, 'url': url,
            'width': width, 'height': height,
            'available': available, 'status': status,
            'focalPoint': {'__typename': 'Point', 'x': 0.5, 'y': 0.5}}


def _requested(**nodes):
    """Wrap nodes as the playback entity of the requested title."""
    return {'__typename': 'Movie', 'videoId': REQUESTED, 'art': nodes}


def _foreign(video_id=FOREIGN, **nodes):
    """Wrap nodes as a second, unrelated entity in the same response."""
    return {'__typename': 'Movie', 'videoId': video_id, 'art': nodes}


def _document(*entities):
    return {'playbackEntities': list(entities), 'unifiedEntities': []}


def test_collect_finds_images_at_any_depth():
    """Image nodes sit under playbackEntities and unifiedEntities at differing depths."""
    data = {'playbackEntities': [{'art': {'image': _image('StoryArt|a-b|en')}}],
            'unifiedEntities': [{'title': {'__typename': 'Title'},
                                 'artwork': {'logo': _image('LOGO_BRANDED_HORIZONTAL|c-d|de')}}]}
    keys = sorted(node['key'] for node in artwork.collect_image_nodes(data))
    assert keys == ['LOGO_BRANDED_HORIZONTAL|c-d|de', 'StoryArt|a-b|en']


def test_collect_ignores_non_image_nodes():
    data = {'unifiedEntities': [{'__typename': 'Title', 'text': 'x'},
                                {'__typename': 'Image', 'key': 'StoryArt|a|en'}]}
    assert len(artwork.collect_image_nodes(data)) == 1


def test_classify_reads_the_prefix_before_the_first_pipe():
    assert artwork.classify_image_key('StoryArt|uuid|en') == 'StoryArt'
    assert artwork.classify_image_key('LOGO_BRANDED_HORIZONTAL|uuid|de') == 'LOGO_BRANDED_HORIZONTAL'


def test_classify_ignores_locale_and_variant_suffixes():
    """The live probe sent 'sdp|uuid|de,BADGE|recently.added|de'."""
    assert artwork.classify_image_key('sdp|uuid|de,BADGE|recently.added|de') == 'sdp'


def test_classify_does_not_require_uuid_shape():
    """Review Focus 5: the key is opaque, not validated as a UUID."""
    assert artwork.classify_image_key('StoryArt|not-a-uuid|en') == 'StoryArt'
    assert artwork.classify_image_key('StoryArt|') == 'StoryArt'


def test_classify_recognises_merch_still():
    """Aenderung 3 of the delta lists MERCH_STILL next to 'sdp'.

    The recorded MERCH_STILL is 342x192, below THUMB_WIDTH, so it reaches no
    Kodi field - but it is a type the server emits, and a classifier that
    answered 'unknown' for it would be lying.
    """
    assert artwork.classify_image_key('MERCH_STILL|uuid|en') == 'MERCH_STILL'


def test_merch_still_reaches_no_kodi_field():
    """Classified, but not booked: no type tuple below names it.

    This is deliberate and documented on KNOWN_ART_TYPES. The test pins that
    it stays that way, so whoever makes the booking decision has to change a
    test rather than discover the behaviour in a listing.
    """
    data = _document(_requested(merch=_image('MERCH_STILL|a|b|en', url='merch.jpg', width=665)))
    assert artwork.extract_art(data, REQUESTED) == NO_ART


def test_classify_returns_none_for_unknown_prefix():
    assert artwork.classify_image_key('AVATAR|uuid|en') is None
    assert artwork.classify_image_key('nonsense') is None


def test_extract_maps_the_three_probed_types():
    """LOGO_BRANDED_HORIZONTAL, StoryArt and sdp are the types the probe returned."""
    data = _document(_requested(
        a=_image('LOGO_BRANDED_HORIZONTAL|c|d|de', url='logo.jpg'),
        b=_image('StoryArt|e|f|en', url='fanart.jpg'),
        c=_image('sdp|g|h|de,BADGE|x|de', url='thumb.jpg', width=665, height=375)))
    art = artwork.extract_art(data, REQUESTED)
    assert art['clearlogo'] == 'logo.jpg'
    assert art['fanart'] == 'fanart.jpg'
    assert art['thumb'] == 'thumb.jpg'


def test_extract_falls_back_to_the_unbranded_logo():
    """LOGO_UNBRANDED_HORIZONTAL shares the uuid with the branded variant."""
    data = _document(_requested(a=_image('LOGO_UNBRANDED_HORIZONTAL|c|d|de', url='plain.jpg')))
    assert artwork.extract_art(data, REQUESTED)['clearlogo'] == 'plain.jpg'


def test_branded_logo_wins_over_unbranded():
    data = _document(_requested(
        a=_image('LOGO_UNBRANDED_HORIZONTAL|c|d|de', url='plain.jpg'),
        b=_image('LOGO_BRANDED_HORIZONTAL|c|d|de', url='brand.jpg')))
    assert artwork.extract_art(data, REQUESTED)['clearlogo'] == 'brand.jpg'


def test_extract_prefers_the_wider_sdp_for_thumb():
    """Review Focus 4: the probe returned sdp twice, 342x192 and 665x375."""
    data = _document(_requested(
        a=_image('sdp|1|x|de', url='small.jpg', width=342, height=192),
        b=_image('sdp|1|x|de', url='large.jpg', width=665, height=375)))
    assert artwork.extract_art(data, REQUESTED)['thumb'] == 'large.jpg'


def test_extract_result_is_independent_of_document_order():
    """Ordering must not decide the outcome, or a server reshuffle changes the art."""
    nodes = {'a': _image('LOGO_BRANDED_HORIZONTAL|c|d|de', url='brand.jpg'),
             'b': _image('sdp|1|x|de', url='small.jpg', width=342, height=192),
             'c': _image('sdp|1|x|de', url='large.jpg', width=665, height=375)}
    forward = artwork.extract_art(_document(_requested(**nodes)), REQUESTED)
    reversed_nodes = {'c': nodes['c'], 'b': nodes['b'], 'a': nodes['a']}
    backward = artwork.extract_art({'playbook': 0, 'playbackEntities': [
        _requested(**reversed_nodes)]}, REQUESTED)
    assert forward == backward


def test_extract_skips_images_without_url():
    """Review Focus 3: available=False or a missing url must not raise."""
    data = _document(_requested(
        a=_image('StoryArt|e|f|en', url=None, available=False),
        b=_image('StoryArt|g|h|en', url='good.jpg')))
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'good.jpg'


def test_extract_yields_no_card_below_the_thumb_cutoff():
    """Netflix serves landscape cards at 342x192; below the cutoff there is no thumb at all."""
    data = _document(_requested(a=_image('sdp|1|x|de', url='small.jpg', width=342, height=192)))
    art = artwork.extract_art(data, REQUESTED)
    assert art['thumb'] == ''
    assert art['landscape'] == ''


def test_landscape_carries_the_same_card_as_thumb():
    """Kodi's landscape slot is a wider card of the same still, not the story art behind it."""
    data = _document(_requested(
        a=_image('StoryArt|e|f|en', url='fanart.jpg', width=1920, height=1080),
        b=_image('sdp|1|x|de', url='card.jpg', width=665, height=375)))
    art = artwork.extract_art(data, REQUESTED)
    assert art['thumb'] == 'card.jpg'
    assert art['landscape'] == 'card.jpg'
    assert art['landscape'] != art['fanart']


def test_extract_prefers_the_widest_card_that_clears_the_cutoff():
    """Two preview cards both clear the cutoff, so the wider one has to win on its own merit."""
    data = _document(_requested(
        a=_image('sdp|1|x|de', url='narrow.jpg', width=665, height=375),
        b=_image('sdp|1|x|de', url='wide.jpg', width=700, height=394)))
    assert artwork.extract_art(data, REQUESTED)['thumb'] == 'wide.jpg'
    reversed_data = _document(_requested(
        a=_image('sdp|1|x|de', url='wide.jpg', width=700, height=394),
        b=_image('sdp|1|x|de', url='narrow.jpg', width=665, height=375)))
    assert artwork.extract_art(reversed_data, REQUESTED)['thumb'] == 'wide.jpg'


def test_clearlogo_prefers_the_widest_branded_logo():
    """The same branded logo arrives at several sizes; a skin composites the largest one."""
    data = _document(_requested(
        a=_image('LOGO_BRANDED_HORIZONTAL|c|d|de', url='narrow.jpg', width=400, height=100),
        b=_image('LOGO_BRANDED_HORIZONTAL|e|f|de', url='wide.jpg', width=1000, height=250)))
    assert artwork.extract_art(data, REQUESTED)['clearlogo'] == 'wide.jpg'


def test_extract_ranks_by_width_and_not_by_height():
    """Cards are not taller when they are wider, so the ranking may only read width."""
    data = _document(_requested(
        a=_image('sdp|1|x|de', url='tall.jpg', width=665, height=900),
        b=_image('sdp|1|x|de', url='wide.jpg', width=1080, height=200)))
    assert artwork.extract_art(data, REQUESTED)['thumb'] == 'wide.jpg'
    # Identical widths tie, and the tie keeps the first of the two rather than the tallest one.
    tied = _document(_requested(
        a=_image('sdp|1|x|de', url='first.jpg', width=665, height=375),
        b=_image('sdp|1|x|de', url='second.jpg', width=665, height=900)))
    assert artwork.extract_art(tied, REQUESTED)['thumb'] == 'first.jpg'


def test_extract_skips_an_unavailable_image_that_still_has_a_url():
    """Netflix leaves a resolved url on an image it is not serving, so the flag has to win."""
    data = _document(_requested(
        a=_image('StoryArt|e|f|en', url='stale.jpg', width=1920, height=1080, available=False),
        b=_image('StoryArt|g|h|en', url='good.jpg', width=665, height=375)))
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'good.jpg'


def test_extract_skips_an_image_whose_url_is_empty():
    """An unserved image can carry an empty string rather than a null, and both must be skipped."""
    data = _document(_requested(
        a=_image('StoryArt|e|f|en', url='', width=1920, height=1080),
        b=_image('StoryArt|g|h|en', url='good.jpg', width=665, height=375)))
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'good.jpg'


def test_collect_ignores_a_non_image_node_that_carries_a_key():
    """DetailModal entities are keyed as well, so a key alone does not identify an image."""
    data = {'unifiedEntities': [{'__typename': 'Title', 'key': 'StoryArt|a|en'},
                                {'__typename': 'Image', 'key': 'StoryArt|b|en'}]}
    assert [node['key'] for node in artwork.collect_image_nodes(data)] == ['StoryArt|b|en']


def test_extract_returns_empty_mapping_for_data_without_images():
    art = artwork.extract_art({'unifiedEntities': [{'__typename': 'Title'}]}, REQUESTED)
    assert art == {'thumb': '', 'landscape': '', 'fanart': '', 'clearlogo': ''}


def test_extract_handles_empty_data():
    assert artwork.extract_art({}, REQUESTED)['thumb'] == ''


# --- entity scoping -------------------------------------------------------
#
# The request enables videoMerchEnabled, hasPromoVideoOverride and
# checkLinearChannel, so a response carries entities other than the requested
# one, and those carry their own videoId / unifiedEntityId. A document-wide
# walk lets the widest foreign image win every field.


def test_a_foreign_entity_does_not_win_the_fanart():
    """A promo video's StoryArt is wider than the title's and must not be booked."""
    data = _document(
        _requested(art=_image('StoryArt|a|b|en', url='title.jpg', width=848, height=477)),
        _foreign(art=_image('StoryArt|c|d|en', url='promo.jpg', width=1920, height=1080)))
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'title.jpg'


def test_a_foreign_entity_does_not_win_the_thumb_or_the_logo():
    """The same leak through the other two fields, so no field is scoped alone."""
    data = _document(
        _requested(card=_image('sdp|a|b|de', url='title-card.jpg', width=665, height=375),
                   logo=_image('LOGO_BRANDED_HORIZONTAL|c|d|de', url='title-logo.jpg',
                               width=625, height=250)),
        _foreign(card=_image('sdp|e|f|de', url='promo-card.jpg', width=1080, height=608),
                 logo=_image('LOGO_BRANDED_HORIZONTAL|g|h|de', url='promo-logo.jpg',
                             width=2000, height=800)))
    art = artwork.extract_art(data, REQUESTED)
    assert art['thumb'] == 'title-card.jpg'
    assert art['landscape'] == 'title-card.jpg'
    assert art['clearlogo'] == 'title-logo.jpg'


def test_a_foreign_entity_alone_yields_no_art_at_all():
    """No requested node means no art - the foreign art is not a substitute."""
    data = _document(_foreign(art=_image('StoryArt|a|b|en', url='promo.jpg', width=1920)))
    assert artwork.extract_art(data, REQUESTED) == NO_ART


def test_the_nearest_entity_wins_over_an_outer_one():
    """A merch entry nested inside the title has its own id, and it wins over the title's.

    delta:550 records videoMerch carrying unifiedEntityId and videoId, so a
    nested merch image is attributed to the merch entry, not to the title the
    entry hangs under.
    """
    data = _document(_requested(
        art=_image('StoryArt|a|b|en', url='title.jpg', width=848),
        videoMerch={'unifiedEntityId': f'Video:{FOREIGN}', 'videoId': FOREIGN,
                    'art': _image('StoryArt|c|d|en', url='merch.jpg', width=1920)}))
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'title.jpg'


def test_an_entity_is_matched_by_its_unified_entity_id():
    """The unified form 'Video:<id>' identifies the same entity as the numeric videoId."""
    data = {'unifiedEntities': [
        {'unifiedEntityId': f'Video:{FOREIGN}', 'artwork': {
            'storyArt': _image('StoryArt|a|b|en', url='foreign.jpg', width=1920)}},
        {'unifiedEntityId': f'Video:{REQUESTED}', 'artwork': {
            'storyArt': _image('StoryArt|c|d|en', url='title.jpg', width=848)}}]}
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'title.jpg'


def test_the_entity_is_matched_as_a_string():
    """get_video_art passes an int, the document carries an int, the caller may pass either."""
    data = _document(_requested(art=_image('StoryArt|a|b|en', url='title.jpg', width=848)))
    assert artwork.extract_art(data, str(REQUESTED))['fanart'] == 'title.jpg'


def test_an_image_no_entity_reaches_is_dropped_while_scoping():
    """Decided and pinned: unattributed nodes are dropped once scoping is active.

    Nothing ties such a node to the requested title, so keeping it would
    reopen the leak the scope exists to close. The document-wide walk
    (video_id=None) is where the raw inventory is still available.
    """
    data = _document(_requested(art=_image('StoryArt|a|b|en', url='title.jpg', width=848)),
                     {'art': _image('StoryArt|c|d|en', url='orphan.jpg', width=1920)})
    assert artwork.extract_art(data, REQUESTED)['fanart'] == 'title.jpg'
    assert len(artwork.collect_image_nodes(data, REQUESTED)) == 1


def test_the_document_wide_walk_keeps_every_entity():
    """Without a requested id nothing is attributed and nothing is excluded."""
    data = _document(_requested(art=_image('StoryArt|a|b|en', url='title.jpg')),
                     _foreign(art=_image('StoryArt|c|d|en', url='promo.jpg')),
                     {'art': _image('StoryArt|e|f|en', url='orphan.jpg')})
    assert len(artwork.collect_image_nodes(data)) == 3


def test_a_document_without_any_entity_id_falls_back_to_the_walk():
    """Decided and pinned: an unidentifiable document is not scoped away.

    If Netflix moved or renamed the id fields, every dict would look like a
    nameless node and scoping would empty the artwork of every title in the
    add-on without a single error. Degrading to the pre-scoping behaviour is
    the visible failure, so that is what happens - and only in that case.
    """
    anonymous = _document({'art': _image('StoryArt|a|b|en', url='anon.jpg', width=848)})
    assert artwork.extract_art(anonymous, REQUESTED)['fanart'] == 'anon.jpg'
    assert artwork.extract_art({}, REQUESTED)['fanart'] == ''


def test_a_foreign_entity_is_not_a_substitute_for_a_missing_one():
    """The scope stays active when the requested title is simply not in the response.

    The document identifies entities, so scoping applies; no node belongs to
    the requested title, so nothing is booked. The promo's still must not fill
    a field the title itself leaves empty.
    """
    data = _document(_foreign(art=_image('StoryArt|a|b|en', url='promo.jpg', width=848)))
    assert artwork.extract_art(data, 99999999)['fanart'] == ''


def test_collect_scopes_by_the_requested_entity():
    """The collector itself filters, so _pick cannot be handed a foreign node."""
    data = _document(
        _requested(art=_image('StoryArt|a|b|en', url='title.jpg')),
        _foreign(art=_image('StoryArt|c|d|en', url='promo.jpg')))
    assert [node['url'] for node in artwork.collect_image_nodes(data, REQUESTED)] == ['title.jpg']
    assert [node['url'] for node in artwork.collect_image_nodes(data)] == ['title.jpg', 'promo.jpg']


def test_entity_scoped_extraction_ignores_document_order():
    """The scope decides the candidate set, not the position of the entities."""
    requested = _requested(art=_image('StoryArt|a|b|en', url='title.jpg', width=848))
    foreign = _foreign(art=_image('StoryArt|c|d|en', url='promo.jpg', width=1920))
    assert (artwork.extract_art(_document(requested, foreign), REQUESTED)
            == artwork.extract_art(_document(foreign, requested), REQUESTED))


def test_a_non_dict_document_yields_nothing():
    """The response body is not validated by the client, so this cannot raise here."""
    assert not artwork.collect_image_nodes(None, REQUESTED)
    assert not artwork.collect_image_nodes(['text'], REQUESTED)
