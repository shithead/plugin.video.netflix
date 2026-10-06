# -*- coding: utf-8 -*-
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Verify that the API-layer modules import without a running Kodi.
"""
import resources.lib.kodi.infolabels
import resources.lib.utils.api_paths
import resources.lib.utils.data_types


def test_api_layer_imports_without_kodi():
    """The three modules under test must be importable"""
    assert resources.lib.utils.api_paths.build_paths is not None
    assert resources.lib.utils.data_types.LoCo is not None
    assert resources.lib.kodi.infolabels.get_art is not None
