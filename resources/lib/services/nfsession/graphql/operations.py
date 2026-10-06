# -*- coding: utf-8 -*-
"""
    Copyright (C) 2026 plugin.video.netflix
    Netflix GraphQL persisted-query catalogue

    All 601 recorded requests across seven network captures carried
    'version: 102' with a persistedQuery id and no inline query string.

    SPDX-License-Identifier: MIT
    See LICENSES/MIT.md for more information.
"""

PERSISTED_VERSION = 102

OPERATIONS = {
    'CLCSInterstitialAccountPages': '03b4bbd1-8fa5-4528-bcee-7d539f207dde',
    'CLCSInterstitialLolomo': '906ae8ae-8f80-4bd9-9fec-4d49dd41fe64',
    'CLCSInterstitialPlaybackAndPostPlayback': '57c07808-0587-450c-8638-368ac009823a',
    'CLCSInterstitialProfileGate': '736340c9-0778-4065-8477-986b012997c6',
    'CarouselPage': 'f75b6cb4-ce3f-41c2-9a79-4d72569299b4',
    'DetailModal': 'e5748389-c3b9-496e-bcea-64883cff1e87',
    'DetailModalTrailers': '06e30ee5-7983-4fef-8135-5914124b76ad',
    'FetchMoreSections': 'befcbda7-28dc-4de5-b35d-dea7387a3583',
    'GetBrowsePage': '7c0f9ff7-ab77-4cb5-8ef7-6f9eff178a87',
    'GetGenreSubgenres': '563f7889-6145-41c4-a335-d3928c9edabd',
    'LinearChannelCheck': '6b737c7d-cb55-4fac-9d7e-fbb01af7c767',
    'MiniModalQuery': 'e68167bb-f301-45a0-94e6-33f47aa333ef',
    'PreviewModalEpisodeSelector': 'dbc3b274-d4f9-4811-aaf1-d082d3b936f2',
    'PreviewModalEpisodeSelectorSeasonEpisodes': '4cf0a279-dd32-454d-9758-486359c0d48b',
    'PreviewModalUnifiedEntity': '38c91a26-6773-4518-aed7-4591969a6705',
    'PreviewModalVideoTitleGroup': 'e8bf3af9-0c4b-49d3-8013-58a26b3fbb89',
    'SearchPageQueryResults': 'c068ad18-089b-418f-a3d7-02d34858bfc0',
    'SetEntityThumbRating': '36a7647d-e3b3-468c-a4e4-43e541e174c6',
    'UpdatePage': '04a0a424-9c01-4932-8c6f-73c6d177a0bc',
    'useProfilesSummaryQuery': '2d907549-08ae-495b-a2c8-6777d38e9e0f',
    'VideoDetailsModalSimilars': '838718e1-85d7-41e6-b637-6a74dfda11d1',
}

DEFAULT_VARIABLES = {
    'DetailModal': {
        'opaqueImageFormat': 'JPG',
        'transparentImageFormat': 'PNG',
        'videoMerchEnabled': True,
        'fetchPromoVideoOverride': False,
        'hasPromoVideoOverride': True,
        'promoVideoId': 0,
        'videoMerchContext': 'BROWSE',
        'isLiveEpisodic': False,
        'includeCroppedLogo': False,
        'checkLinearChannel': True,
        'textEvidenceUiContext': 'ODP',
        'artworkContext': {},
    },
    'useProfilesSummaryQuery': {
        'profileIconSize': 'SQUARE_320',
    },
}
