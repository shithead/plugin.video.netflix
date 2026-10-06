# -*- coding: utf-8 -*-
"""
    Copyright (C) 2026 plugin.video.netflix
    Map Netflix GraphQL artwork onto Kodi art fields

    Artwork arrives as nodes of __typename 'Image' with a key of the form
    '<ArtType>|<uuid>|<locale>[|<variant>]'. The key is opaque: it is never
    validated as a UUID, and the locale or variant suffixes are ignored.

    SPDX-License-Identifier: MIT
    See LICENSES/MIT.md for more information.
"""

KNOWN_ART_TYPES = ('LOGO_BRANDED_HORIZONTAL', 'LOGO_UNBRANDED_HORIZONTAL', 'StoryArt', 'sdp',
                   'MERCH_STILL')
"""Every art type prefix the recorded responses carry.

MERCH_STILL is classified but never booked: no tuple below names it, so it
reaches no Kodi slot. Aenderung 3 of the delta lists it next to 'sdp' as a
card source, and the only recorded MERCH_STILL is 342x192 - below THUMB_WIDTH,
so booking it would yield nothing anyway. It is recorded here rather than in
the booking tuples because the server does emit it, and a caller that asks
'which art type is this key' must get a truthful answer. Booking it is a
decision the wiring task has to make, not a side effect of this list.
"""

CLEARTLOGO_TYPES = ('LOGO_BRANDED_HORIZONTAL', 'LOGO_UNBRANDED_HORIZONTAL')
FANART_TYPES = ('StoryArt',)
THUMB_TYPES = ('sdp',)

THUMB_WIDTH = 400
"""Landscape cards arrive at 342x192; the preview variant at 665x375.

This is a cutoff and not a preference: sdp nodes narrower than this are
dropped outright, so a response carrying only 342-wide cards yields no thumb
and no landscape rather than a degraded image.
"""

EMPTY_ART = {'thumb': '', 'landscape': '', 'fanart': '', 'clearlogo': ''}
"""The art key set with every value empty.

The one declaration of the key set: extract_art() starts from it and
get_video_art() returns it when a lookup fails. Callers splat the result into
parse_art(), which reads only the keys it knows - a key added to one copy of
this mapping but not the other would vanish without an error. Never hand this
object out, return a copy, because the caller may modify the result.
"""


def classify_image_key(key):
    """Return the art type of an Image key, or None when it is not recognised.

    :param key: the node's 'key' field, '<ArtType>|<uuid>|<locale>[|<variant>]'
    :return the part before the first pipe, or None
    """
    art_type = str(key or '').split('|', 1)[0]
    return art_type if art_type in KNOWN_ART_TYPES else None


def collect_image_nodes(data, video_id=None):
    """Return the Image nodes in scope, in document order.

    An Image node belongs to an entity when the nearest ancestor dict carrying
    a videoId or a unifiedEntityId names that entity. The NEAREST ancestor
    wins, so a videoMerch entry or a promo video nested inside the requested
    title - both of which carry their own ids, delta Aenderung 3 - has its
    images attributed to itself and not to the title around it.

    video_id decides the scope:

    - None walks the whole document. Nothing is attributed and nothing is
      excluded, which is what a caller that wants the raw inventory wants.
    - an id scopes the walk to that entity. An Image node that no identified
      entity reaches is then DROPPED: nothing ties it to the requested title,
      and keeping it would reopen the leak the scope closes. A response that
      carries the requested title but no art for it therefore yields no art,
      which is correct - the promo's still is not a substitute for it.
    - a document in which NO entity can be identified at all is walked
      document-wide instead. That is the shape Netflix would have if it moved
      or renamed the id fields, and scoping a document whose entities cannot
      be named would silently empty the artwork of every title in the add-on
      without a single error anywhere. Degrading to the pre-scoping behaviour
      is visible - the wrong picture can be booked - while degrading to
      nothing is not.

    :param data: the parsed 'data' object of a GraphQL response
    :type data: dict
    :param video_id: the id of the requested title, None for no scoping
    :type video_id: int|str|None
    :return: the Image nodes in scope, in document order
    :rtype: list
    """
    found = []
    wanted = str(video_id) if video_id is not None and _identifies_any_entity(data) else None
    _collect(data, None, wanted, found)
    return found


def extract_art(data, video_id):
    """Map the Image nodes of a GraphQL response onto Kodi art fields.

    Only the nodes of the requested entity are considered, see
    collect_image_nodes() for how an Image node is attributed to an entity
    and for what happens when the entity is not in the response.

    :param data: the parsed 'data' object of a DetailModal response
    :type data: dict
    :param video_id: the id of the requested title
    :type video_id: int|str
    :return a dict with the keys thumb, landscape, fanart and clearlogo
    """
    nodes = collect_image_nodes(data, video_id)
    clearlogo = _pick(nodes, CLEARTLOGO_TYPES, prefer=['LOGO_BRANDED_HORIZONTAL'])
    fanart = _pick(nodes, FANART_TYPES)
    thumb = _pick(nodes, THUMB_TYPES, min_width=THUMB_WIDTH)
    return dict(EMPTY_ART, thumb=thumb, landscape=thumb, fanart=fanart, clearlogo=clearlogo)


def _pick(nodes, art_types, prefer=None, min_width=0):
    """Choose the best URL among Image nodes of the given types.

    Nodes are discarded first: a node with no url, with 'available' False or
    with a width below min_width never reaches the comparison. When nothing
    survives, the result is ''.

    Among the survivors, 'prefer' decides if given: the first of its art types
    that has a candidate supplies the url, taking that type's widest node.
    Without 'prefer', the widest node across all the given types supplies it.
    Both branches rank by width alone, so the result does not depend on the
    order in which the nodes appeared in the document.

    min_width is a cutoff rather than a preference, so a type whose nodes are
    all below it contributes nothing instead of a smaller image.

    :param nodes: the in-scope Image nodes, already attributed to one entity
    :type nodes: list
    :param art_types: the art types this Kodi field may be booked from
    :type art_types: tuple
    :param prefer: art types in order of precedence, the first with a candidate wins
    :type prefer: list|None
    :param min_width: a width below which a node does not count at all
    :type min_width: int
    :return: the chosen url, an empty string when nothing qualifies
    :rtype: str
    """
    candidates = {}
    for node in nodes:
        art_type = classify_image_key(node.get('key'))
        if art_type not in art_types:
            continue
        url = node.get('url')
        if not url or node.get('available') is False:
            continue
        width = node.get('width') or 0
        if width < min_width:
            continue
        candidates.setdefault(art_type, []).append((width, url))
    if not candidates:
        return ''
    if prefer:
        for art_type in prefer:
            if art_type in candidates:
                return max(candidates[art_type], key=lambda item: item[0])[1]
    return max((item for entries in candidates.values() for item in entries),
               key=lambda item: item[0])[1]


def _entity_id(node):
    """Return the entity a dict identifies itself with, as a plain id string.

    Both forms the responses use are read: the numeric 'videoId' and the
    'unifiedEntityId' of the form 'Video:80057281'. The type prefix of the
    unified id is dropped, because ids are unique across entity types, so
    'Show:80057281' can only ever be the entity 80057281.

    :param node: any dict of a GraphQL response
    :type node: dict
    :return: the id the dict identifies, an empty string when it identifies none
    :rtype: str
    """
    video_id = node.get('videoId')
    if video_id is not None:
        return str(video_id)
    unified_entity_id = node.get('unifiedEntityId')
    if unified_entity_id is not None:
        return str(unified_entity_id).rsplit(':', 1)[-1]
    return ''


def _identifies_any_entity(node):
    """Return whether any dict in a structure identifies an entity at all.

    :param node: a nested response structure
    :return: True when at least one dict carries a videoId or a unifiedEntityId
    :rtype: bool
    """
    if isinstance(node, dict):
        return bool(_entity_id(node)) or any(_identifies_any_entity(value) for value in node.values())
    if isinstance(node, list):
        return any(_identifies_any_entity(value) for value in node)
    return False


def _collect(node, owner, wanted, found):
    """Append the in-scope Image nodes of a structure to the found list.

    'owner' is the entity of the nearest identified ancestor, '' while none has
    been seen. It is replaced - not merged - by the id of a dict that carries
    one, which is what makes the nearest ancestor win over an outer one.

    :param node: a nested response structure
    :param owner: the id of the nearest identified ancestor, '' when there is none
    :type owner: str
    :param wanted: the requested entity id, None to keep every node
    :type wanted: str|None
    :param found: the list the in-scope nodes are appended to
    :type found: list
    """
    if isinstance(node, dict):
        owner = _entity_id(node) or owner
        if node.get('__typename') == 'Image' and (wanted is None or owner == wanted):
            found.append(node)
        for value in node.values():
            _collect(value, owner, wanted, found)
    elif isinstance(node, list):
        for value in node:
            _collect(value, owner, wanted, found)
