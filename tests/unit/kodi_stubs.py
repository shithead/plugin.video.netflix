# -*- coding: utf-8 -*-
# The stubs deliberately cover the whole API-layer import surface (see below), which
# makes this module longer than the pylint default allows.
# pylint: disable=too-many-lines
"""
    Copyright (C) 2025 plugin.video.netflix

    SPDX-License-Identifier: GPL-3.0-only
    See LICENSES/GPL-3.0-only.md for more information.
    Kodi API stubs for the unit test suite

    The add-on modules can only be imported inside Kodi, because they import the
    `xbmc*` modules at module level. This module provides stand-ins for those
    modules and registers them in `sys.modules`.

    :func:`install` must be called before any `resources.lib` module is imported:
    several of the stubbed names are evaluated while the production modules are
    loaded (default argument values, type annotations and base classes), not while
    their functions are called.

    Scope
    -----
    These stubs cover far more of the Kodi API than the import hull of `api_paths`,
    `data_types` and `infolabels` alone needs. They were sized against the **whole
    API layer** of the add-on, so that every module a later unit test is likely to
    touch is importable without Kodi:

    - `resources.lib.globals`, `resources.lib.common` (incl. `kodi_ops`,
      `kodi_wrappers`, `ipc`, `pathops`, `cache_utils`)
    - `resources.lib.utils.*` (`api_paths`, `api_requests`, `data_types`, `esn`,
      `logging`, `cookies`, `website`)
    - `resources.lib.kodi.*` (`infolabels`, `ui.*`, `library_utils`, `nfo`, ...)
    - `resources.lib.navigation.directory_utils`,
      `resources.lib.services.nfsession.nfsession_ops`

    The hull of a single module is not predictable (one added import in an
    intermediate module changes it, and `resources.lib.globals` pulls in much of
    the package anyway), so the broader set is intentional. The stubs are confined
    to `tests/` and cost nothing at runtime.

    Not covered (and not needed by the unit tests so far):
    `resources.lib.services.playback.action_controller` and
    `resources.lib.services.playback.am_stream_continuity` need further
    `xbmc.Player` methods (`setAudioStream`, `setSubtitleStream`, `showSubtitles`),
    `resources.lib.services.http_server` is out of scope, `resources.lib.database.db_*_mysql`
    needs the `mysql` module, `resources.lib.services.nfsession.msl.default_crypto`
    needs `Crypto`, and `resources.lib.kodi.context_menu_utils` /
    `resources.lib.navigation.directory_search` read `G.ADDON` at import time,
    which no stub can satisfy before the fixture runs.

    Adding coverage here is therefore expected; so is the fact that a few stubbed
    names (`xbmc.getRegion`, `xbmcgui.CONTROL_BUTTON`, `xbmcvfs.validatePath`, ...)
    are currently unused by the production code and exist only as a safety net.
    """
import logging
import os
import sys
import types

# Directory holding the runtime scripts of the add-on (AddonSignals.py and friends)
TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Log level names and severities of the real xbmc module
LOG_LEVELS = {
    'LOGDEBUG': 0,
    'LOGINFO': 1,
    'LOGWARNING': 2,
    'LOGERROR': 3,
    'LOGFATAL': 4,
    'LOGNONE': 5,
}


def _new_module(name):
    """
    Create an empty stand-in for a Kodi module

    :param name: name of the module to create
    :type name: str
    :return: an empty module registered as `name`
    :rtype: types.ModuleType
    """
    module = types.ModuleType(name)
    module.__doc__ = f'Test stub of the Kodi module {name}'
    return module


class _Stub:
    """
    Base class of the stubbed Kodi classes

    It keeps every keyword argument it is constructed with as an attribute, so
    that tests can assert on the values the production code passed in.
    """

    def __init__(self, *args, **kwargs):
        """
        Store the constructor arguments as instance attributes

        :param args: positional arguments given by the production code
        :type args: tuple
        :param kwargs: keyword arguments given by the production code
        :type kwargs: dict
        """
        self._args = args
        self._kwargs = dict(kwargs)
        self.__dict__.update(kwargs)
        if args and not hasattr(self, 'label'):
            self.label = args[0]


class Monitor:
    """
    Stub of xbmc.Monitor

    `tests/AddonSignals.py` subclasses it at import time, so it has to be a
    real class.
    """

    def __init__(self, *args, **kwargs):
        """Accept and ignore any argument, as the Kodi class does"""
        self._args = args
        self._kwargs = dict(kwargs)
        self.aborted = False

    def abortRequested(self):  # pylint: disable=invalid-name
        """
        Report whether Kodi requested the add-on to abort

        :return: always False, no Kodi is running to request an abort
        :rtype: bool
        """
        return False

    def waitForAbort(self, timeout=0):  # pylint: disable=invalid-name
        """
        Wait for an abort request

        :param timeout: maximum time to wait in seconds
        :type timeout: float
        :return: always False, no Kodi is running to request an abort
        :rtype: bool
        """
        del timeout
        return False

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        """Called by Kodi on settings changes"""

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """
        Called by Kodi on notifications

        :param sender: id of the notification sender
        :type sender: str
        :param method: name of the notification method
        :type method: str
        :param data: payload of the notification
        :type data: str
        """
        del sender, method, data


class Player(_Stub):
    """
    Stub of xbmc.Player
    """

    def __init__(self, *args, **kwargs):
        """
        Create a player that never plays anything

        :param args: positional arguments given by the production code
        :type args: tuple
        :param kwargs: keyword arguments given by the production code
        :type kwargs: dict
        """
        super().__init__(*args, **kwargs)
        self._playing = False
        self._file = ''

    def play(self, item=None, listitem=None, windowed=False, startpos=-1):
        """
        Pretend to play an item

        :param item: the item to play
        :type item: str
        :param listitem: the list item to play
        :type listitem: xbmcgui.ListItem
        :param windowed: whether to play windowed
        :type windowed: bool
        :param startpos: start position in seconds
        :type startpos: int
        """
        del windowed, startpos
        self._file = item if item is not None else getattr(listitem, 'path', '')
        self._playing = True

    def stop(self):
        """Stop playback"""
        self._playing = False
        self._file = ''

    def pause(self):
        """Pause playback"""
        self._playing = False

    def isPlaying(self):  # pylint: disable=invalid-name
        """
        Report whether something is playing

        :return: True if play() has been called without stop()
        :rtype: bool
        """
        return self._playing

    def getPlayingFile(self):  # pylint: disable=invalid-name
        """
        Return the path of the current playing item

        :return: the path passed to play()
        :rtype: str
        """
        return self._file

    def getTime(self):  # pylint: disable=invalid-name
        """
        Return the current playback position

        :return: always 0
        :rtype: float
        """
        return 0.0

    def getTotalTime(self):  # pylint: disable=invalid-name
        """
        Return the total duration of the current playing item

        :return: always 0
        :rtype: float
        """
        return 0.0

    def seekTime(self, seekTime):  # pylint: disable=invalid-name
        """
        Seek to the given position

        :param seekTime: the position in seconds
        :type seekTime: float
        """
        del seekTime

    def onPlayBackStarted(self):  # pylint: disable=invalid-name
        """Called by Kodi when playback started"""

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """Called by Kodi when playback stopped"""

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """Called by Kodi when playback ended"""

    def onPlayBackPaused(self):  # pylint: disable=invalid-name
        """Called by Kodi when playback paused"""

    def onPlayBackResumed(self):  # pylint: disable=invalid-name
        """Called by Kodi when playback resumed"""

    def onPlayBackSeek(self, seekTime, seekOffset):  # pylint: disable=invalid-name
        """
        Called by Kodi on seek

        :param seekTime: the new position in seconds
        :type seekTime: float
        :param seekOffset: the seek offset in seconds
        :type seekOffset: float
        """
        del seekTime, seekOffset


class ListItem(_Stub):
    """
    Stub of xbmcgui.ListItem

    `resources.lib.common.kodi_wrappers.ListItemW` derives from it, so all
    attributes used there have to exist.
    """

    def __init__(self, label='', label2='', path='', offscreen=False):
        """
        Store label, label, path and offscreen flag

        :param label: the primary label of the item
        :type label: str
        :param label2: the secondary label of the item
        :type label2: str
        :param path: the path of the item
        :type path: str
        :param offscreen: whether rendering is skipped
        :type offscreen: bool
        """
        super().__init__(label, label2, path, offscreen)
        self.label = label
        self.label2 = label2
        self.path = path
        self.offscreen = offscreen
        self.info = {}
        self.art = {}
        self.properties = {}
        self.stream_info = []
        self.subtitles = []
        self.context_menu = []
        self.mimetype = ''
        self.is_folder = False
        self.content_lookup = False
        self.selected = False

    def getLabel(self):  # pylint: disable=invalid-name
        """
        Return the primary label

        :return: the primary label
        :rtype: str
        """
        return self.label

    def getLabel2(self):  # pylint: disable=invalid-name
        """
        Return the secondary label

        :return: the secondary label
        :rtype: str
        """
        return self.label2

    def setLabel(self, label):  # pylint: disable=invalid-name
        """
        Set the primary label

        :param label: the new primary label
        :type label: str
        """
        self.label = label

    def setLabel2(self, label):  # pylint: disable=invalid-name
        """
        Set the secondary label

        :param label: the new secondary label
        :type label: str
        """
        self.label2 = label

    def getPath(self):  # pylint: disable=invalid-name
        """
        Return the path of the item

        :return: the path of the item
        :rtype: str
        """
        return self.path

    def setPath(self, path):  # pylint: disable=invalid-name
        """
        Set the path of the item

        :param path: the new path of the item
        :type path: str
        """
        self.path = path

    def setInfo(self, type, infoLabels):  # pylint: disable=redefined-builtin,invalid-name
        """
        Store the given info labels

        :param type: type of the info labels ('video', 'music', 'game')
        :type type: str
        :param infoLabels: the info labels to store
        :type infoLabels: dict
        """
        del type
        self.info.update(infoLabels)

    def getArt(self, key):  # pylint: disable=invalid-name
        """
        Return a single artwork entry

        `resources.lib.common.kodi_wrappers.ListItemW.getArt` delegates here on a
        client instance, so this method is needed as soon as art is read.

        :param key: name of the artwork entry
        :type key: str
        :return: the artwork url or an empty string
        :rtype: str
        """
        return self.art.get(key, '')

    def setArt(self, dictionary):  # pylint: disable=invalid-name
        """
        Store the given artwork

        :param dictionary: the artwork to store
        :type dictionary: dict
        """
        self.art.update(dictionary)

    def isSelected(self):  # pylint: disable=invalid-name
        """
        Report whether the item is selected

        :return: True if select(True) has been called
        :rtype: bool
        """
        return self.selected

    def addStreamInfo(self, cType, dictionary):  # pylint: disable=invalid-name
        """
        Store a single stream info entry

        :param cType: type of the stream ('video', 'audio', 'subtitle')
        :type cType: str
        :param dictionary: the stream info to store
        :type dictionary: dict
        """
        self.stream_info.append((cType, dictionary))

    def setProperty(self, key, value):  # pylint: disable=invalid-name
        """
        Store a property

        :param key: name of the property
        :type key: str
        :param value: value of the property
        :type value: str
        """
        self.properties[key] = value

    def getProperty(self, key):  # pylint: disable=invalid-name
        """
        Return a property

        :param key: name of the property
        :type key: str
        :return: the value of the property or an empty string
        :rtype: str
        """
        return self.properties.get(key, '')

    def setProperties(self, dictionary):  # pylint: disable=invalid-name
        """
        Store multiple properties

        :param dictionary: the properties to store
        :type dictionary: dict
        """
        self.properties.update(dictionary)

    def setSubtitles(self, subtitleFiles):  # pylint: disable=invalid-name
        """
        Store the external subtitles

        :param subtitleFiles: paths of the subtitle files
        :type subtitleFiles: list
        """
        self.subtitles = list(subtitleFiles)

    def setContentLookup(self, enable):  # pylint: disable=invalid-name
        """
        Enable or disable the content lookup of the path

        :param enable: whether the lookup is enabled
        :type enable: bool
        """
        self.content_lookup = enable

    def setMimeType(self, mimetype):  # pylint: disable=invalid-name
        """
        Set the mime type of the item

        :param mimetype: the new mime type
        :type mimetype: str
        """
        self.mimetype = mimetype

    def setIsFolder(self, isFolder):  # pylint: disable=invalid-name
        """
        Mark the item as a folder or as playable content

        :param isFolder: True if the item is a folder
        :type isFolder: bool
        """
        self.is_folder = isFolder

    def addContextMenuItems(self, items, replaceItems=False):  # pylint: disable=invalid-name
        """
        Add entries to the context menu

        :param items: the context menu entries
        :type items: list
        :param replaceItems: whether the existing entries are replaced
        :type replaceItems: bool
        """
        self.context_menu = list(items) if replaceItems else self.context_menu + list(items)

    def select(self, selected):  # pylint: disable=invalid-name
        """
        Mark the item as selected or deselected

        :param selected: True if the item is selected
        :type selected: bool
        """
        self.selected = selected

    def getVideoInfoTag(self):  # pylint: disable=invalid-name
        """
        Return the video info tag of the item

        :return: a new video info tag object
        :rtype: xbmc.InfoTagVideo
        """
        return InfoTagVideo()

    def getMusicInfoTag(self):  # pylint: disable=invalid-name
        """
        Return the music info tag of the item

        :return: a new music info tag object
        :rtype: xbmc.InfoTagMusic
        """
        return InfoTagMusic()

    def getPlayerInfoTag(self):  # pylint: disable=invalid-name
        """
        Return the player info tag of the item

        :return: a new player info tag object
        :rtype: xbmc.InfoTagPlayer
        """
        return InfoTagPlayer()


class Window(_Stub):
    """
    Stub of xbmcgui.Window
    """

    def __init__(self, existingWindowId=-1):  # pylint: disable=invalid-name
        """
        Store the id of the represented window

        :param existingWindowId: id of an existing window to reuse
        :type existingWindowId: int
        """
        super().__init__(existingWindowId)
        self.windowId = existingWindowId
        self.properties = {}

    def getProperty(self, key):  # pylint: disable=invalid-name
        """
        Return a window property

        :param key: name of the property
        :type key: str
        :return: the value of the property or an empty string
        :rtype: str
        """
        return self.properties.get(key, '')

    def setProperty(self, key, value):  # pylint: disable=invalid-name
        """
        Store a window property

        :param key: name of the property
        :type key: str
        :param value: value of the property
        :type value: str
        """
        self.properties[key] = value

    def clearProperty(self, key):  # pylint: disable=invalid-name
        """
        Remove a window property

        :param key: name of the property
        :type key: str
        """
        self.properties.pop(key, None)

    def getFocusId(self):  # pylint: disable=invalid-name
        """
        Return the id of the focused control

        :return: always 0
        :rtype: int
        """
        return 0

    def close(self):
        """Close the window"""

    def show(self):
        """Show the window"""

    def doModal(self):  # pylint: disable=invalid-name
        """Show the window modally"""

    def clearList(self):  # pylint: disable=invalid-name
        """Remove all entries of the window"""


class WindowXMLDialog(_Stub):
    """
    Stub of xbmcgui.WindowXMLDialog
    """

    def __init__(self, *args, **kwargs):
        """
        Store the arguments needed to load the dialog

        The real `xbmcgui.WindowXMLDialog` takes its arguments positionally, so they
        are recorded under the names Kodi documents them with, instead of being bound
        to keyword arguments.

        :param args: positional arguments given by the production code, being the xml
                     file name, the script path, the default skin and the resolution
        :type args: tuple
        :param kwargs: further keyword arguments given by the production code
        :type kwargs: dict
        """
        super().__init__(*args, **kwargs)
        defaults = ('', '', 'Default', '720p')
        names = ('xmlFilename', 'scriptPath', 'defaultSkin', 'defaultRes')
        for position, name in enumerate(names):
            setattr(self, name, args[position] if position < len(args) else defaults[position])


class Dialog(_Stub):
    """
    Stub of xbmcgui.Dialog
    """

    def ok(self, heading, line1='', line2='', line3=''):
        """
        Show an ok dialog

        :param heading: title of the dialog
        :type heading: str
        :param line1: first line of the message
        :type line1: str
        :param line2: second line of the message
        :type line2: str
        :param line3: third line of the message
        :type line3: str
        :return: the index of the pressed button
        :rtype: int
        """
        del heading, line1, line2, line3
        return -1

    def yesno(self, heading, line1='', line2='', line3='', nolabel='', yeslabel=''):
        """
        Show a yes/no dialog

        :param heading: title of the dialog
        :type heading: str
        :param line1: first line of the message
        :type line1: str
        :param line2: second line of the message
        :type line2: str
        :param line3: third line of the message
        :type line3: str
        :param nolabel: label of the no button
        :type nolabel: str
        :param yeslabel: label of the yes button
        :type yeslabel: str
        :return: True if yes was pressed
        :rtype: bool
        """
        del heading, line1, line2, line3, nolabel, yeslabel
        return False

    def select(self, heading, options, **kwargs):
        """
        Show a selection dialog

        :param heading: title of the dialog
        :type heading: str
        :param options: the selectable options
        :type options: list
        :param kwargs: further arguments given by the production code
        :type kwargs: dict
        :return: always -1, nothing was selected
        :rtype: int
        """
        del heading, options, kwargs
        return -1

    def contextmenu(self, options):
        """
        Show a context menu

        :param options: the selectable options
        :type options: list
        :return: always -1, nothing was selected
        :rtype: int
        """
        del options
        return -1

    def multiselect(self, heading, options, **kwargs):
        """
        Show a multiple selection dialog

        :param heading: title of the dialog
        :type heading: str
        :param options: the selectable options
        :type options: list
        :param kwargs: further arguments given by the production code
        :type kwargs: dict
        """
        del heading, options, kwargs

    def notification(self, heading, message, icon='', time=5000, sound=True):
        """
        Show a notification

        :param heading: title of the notification
        :type heading: str
        :param message: text of the notification
        :type message: str
        :param icon: icon of the notification
        :type icon: str
        :param time: display time in milliseconds
        :type time: int
        :param sound: whether a sound is played
        :type sound: bool
        """
        del heading, message, icon, time, sound

    def input(self, heading, defaultt='', type=0, option=0, autoclose=0):  # pylint: disable=redefined-builtin
        """
        Ask for a text input

        :param heading: title of the dialog
        :type heading: str
        :param defaultt: pre-filled text
        :type defaultt: str
        :param type: type of the input
        :type type: int
        :param option: additional input option
        :type option: int
        :param autoclose: time in seconds after which the dialog closes
        :type autoclose: int
        :return: always an empty string, nothing was entered
        :rtype: str
        """
        del heading, defaultt, type, option, autoclose
        return ''

    def numeric(self, type, heading, defaultt='', bMask=False):  # pylint: disable=redefined-builtin
        """
        Ask for a numeric input

        :param type: type of the input
        :type type: int
        :param heading: title of the dialog
        :type heading: str
        :param defaultt: pre-filled value
        :type defaultt: str
        :param bMask: whether the input is masked
        :type bMask: bool
        :return: always an empty string, nothing was entered
        :rtype: str
        """
        del type, heading, defaultt, bMask
        return ''

    def textviewer(self, heading, text='', usemono=False):
        """
        Show a text viewer

        :param heading: title of the dialog
        :type heading: str
        :param text: the shown text
        :type text: str
        :param usemono: whether a monospace font is used
        :type usemono: bool
        """
        del heading, text, usemono

    def browse(self, type, heading, shares, mask='', useThumbs=False,  # pylint: disable=redefined-builtin
               treatAsFolder=False, defaultt='', enableMultiple=False):
        """
        Show a browse dialog

        :param type: type of the browse dialog
        :type type: int
        :param heading: title of the dialog
        :type heading: str
        :param shares: the browsable shares
        :type shares: str
        :param mask: mask of the file types to show
        :type mask: str
        :param useThumbs: whether thumbnails are used
        :type useThumbs: bool
        :param treatAsFolder: whether files are treated as folders
        :type treatAsFolder: bool
        :param defaultt: pre-selected path
        :type defaultt: str
        :param enableMultiple: whether multiple entries can be selected
        :type enableMultiple: bool
        :return: always an empty string, nothing was selected
        :rtype: str
        """
        del type, heading, shares, mask, useThumbs, treatAsFolder, defaultt, enableMultiple
        return ''

    def close(self):
        """Close the dialog"""


class DialogProgress(_Stub):
    """
    Stub of xbmcgui.DialogProgress
    """

    def create(self, heading, message=''):
        """
        Open the progress dialog

        :param heading: title of the dialog
        :type heading: str
        :param message: text of the dialog
        :type message: str
        """
        del heading, message

    def update(self, percent, message=''):
        """
        Update the progress dialog

        :param percent: progress in percent
        :type percent: int
        :param message: text of the dialog
        :type message: str
        """
        del percent, message

    def close(self):
        """Close the progress dialog"""

    def iscanceled(self):  # pylint: disable=invalid-name
        """
        Report whether the user cancelled the dialog

        :return: always False, no user is present
        :rtype: bool
        """
        return False


class DialogProgressBG(DialogProgress):  # pylint: disable=invalid-name
    """
    Stub of xbmcgui.DialogProgressBG
    """


class _InfoTag:
    """
    Base class of the stubbed xbmc InfoTag classes

    All setters record their arguments, so that tests can assert on the infolabels
    the production code passed in.
    """

    #: Prefix of the attributes the arguments are recorded in
    _PREFIX = ''

    def __init__(self, *args):
        """
        Initialise the recorded attributes

        The InfoTag classes of the real `xbmc` module take no arguments, so no
        keyword arguments are accepted here either.

        :param args: positional arguments given by the production code
        :type args: tuple
        """
        self._args = args
        self._values = {}

    def _set(self, name, *values):
        """
        Record the values of an infolabel setter

        :param name: name of the setter
        :type name: str
        :param values: the values passed to the setter
        :type values: tuple
        """
        self._values[name] = list(values)

    def _get(self, name):
        """
        Return the recorded values of an infolabel setter

        :param name: name of the setter
        :type name: str
        :return: the recorded values or an empty list
        :rtype: list
        """
        return self._values.get(name, [])

    def as_dict(self):
        """
        Return all recorded infolabel values

        :return: mapping of setter name to the values passed to it
        :rtype: dict
        """
        return dict(self._values)

    def __getattr__(self, name):
        """
        Answer every unknown setter with a recorder

        This keeps the stub usable for all infolabels of the Kodi API, also for
        those that are not known here.

        :param name: name of the requested attribute
        :type name: str
        :return: a function recording its arguments
        :rtype: func
        """
        if name.startswith('get'):
            return lambda *args: []
        if name.startswith('set') or name.startswith('add'):
            def _recorder(*args, **kwargs):
                """Record the given values"""
                del kwargs
                self._set(name, *args)
            return _recorder
        raise AttributeError(f'{self.__class__.__name__} has no attribute {name}')


class InfoTagVideo(_InfoTag):  # pylint: disable=invalid-name
    """
    Stub of xbmc.InfoTagVideo
    """


class InfoTagMusic(_InfoTag):  # pylint: disable=invalid-name
    """
    Stub of xbmc.InfoTagMusic
    """


class InfoTagPlayer(_InfoTag):  # pylint: disable=invalid-name
    """
    Stub of xbmc.InfoTagPlayer
    """


class StreamDetail(_Stub):
    """
    Stub of the xbmc stream detail classes

    Covers xbmc.VideoStreamDetail, xbmc.AudioStreamDetail and
    xbmc.SubtitleStreamDetail.
    """


class Actor(_Stub):
    """
    Stub of xbmc.Actor
    """

    def __init__(self, name='', role='', thumbnail='', order=0, **kwargs):
        """
        Store the actor details

        :param name: name of the actor
        :type name: str
        :param role: role of the actor
        :type role: str
        :param thumbnail: thumbnail of the actor
        :type thumbnail: str
        :param order: order of the actor in the cast list
        :type order: int
        :param kwargs: further arguments given by the production code
        :type kwargs: dict
        """
        super().__init__(name=name, role=role, thumbnail=thumbnail, order=order, **kwargs)
        self.name = name
        self.role = role
        self.thumbnail = thumbnail
        self.order = order


class Addon(_Stub):
    """
    Stub of xbmcaddon.Addon

    The real class reads the add-on settings and metadata of the installed
    add-on, which is not available outside Kodi. The single instance of this
    class returns empty settings, so that the production code falls back to its
    own defaults. Tests that need settings should use the `globals_stub`
    fixture of `tests/unit/conftest.py` instead.
    """

    #: Metadata returned by getAddonInfo()
    INFO = {
        'id': 'plugin.video.netflix',
        'name': 'Netflix',
        'version': '1.0.0',
        'path': '',
        'profile': '',
        'type': 'xbmc.python.pluginsource',
        'author': 'plugin.video.netflix',
    }

    def __init__(self, id=None):  # pylint: disable=invalid-name,redefined-builtin
        """
        Store the id of the add-on

        :param id: id of the add-on to represent
        :type id: str
        """
        super().__init__(id)
        self.id = id or self.INFO['id']
        self._settings = {}

    def getSetting(self, setting):  # pylint: disable=invalid-name
        """
        Return the value of an add-on setting

        :param setting: name of the setting
        :type setting: str
        :return: the stored value or an empty string
        :rtype: str
        """
        return self._settings.get(setting, '')

    def getSettingInt(self, setting):  # pylint: disable=invalid-name
        """
        Return the integer value of an add-on setting

        :param setting: name of the setting
        :type setting: str
        :return: the stored value or 0
        :rtype: int
        """
        try:
            return int(self._settings.get(setting, 0))
        except (TypeError, ValueError):
            return 0

    def getSettingBool(self, setting):  # pylint: disable=invalid-name
        """
        Return the boolean value of an add-on setting

        :param setting: name of the setting
        :type setting: str
        :return: the stored value or False
        :rtype: bool
        """
        return str(self._settings.get(setting, '')).lower() == 'true'

    def setSetting(self, setting, value):  # pylint: disable=invalid-name
        """
        Store the value of an add-on setting

        :param setting: name of the setting
        :type setting: str
        :param value: value of the setting
        :type value: str
        """
        self._settings[setting] = value

    def getLocalizedString(self, msgctxt):  # pylint: disable=invalid-name
        """
        Return the localized string of a message id

        :param msgctxt: id of the message
        :type msgctxt: int
        :return: the message id as string
        :rtype: str
        """
        return str(msgctxt)

    def getAddonInfo(self, info):  # pylint: disable=invalid-name
        """
        Return the metadata of the add-on

        :param info: name of the metadata entry
        :type info: str
        :return: the value of the metadata entry or an empty string
        :rtype: str
        """
        return self.INFO.get(info, '')


def _log(msg, level=0):
    """
    Write a message to the Python logger instead of the Kodi log

    :param msg: the message to log
    :type msg: str
    :param level: severity of the message, using the xbmc log levels
    :type level: int
    """
    logging.getLogger('xbmc').log(logging.DEBUG + (level or 0), '%s', msg)


def _identity(value):
    """
    Return the given value unchanged

    Stands in for the path translation calls of `xbmc`, which return their input
    on every platform a test runs on.

    :param value: the value to return
    :type value: any
    :return: the given value
    :rtype: any
    """
    return value


def _empty_string(*_args, **_kwargs):
    """
    Return an empty string

    Stands in for the info label calls of `xbmc`, which never report anything in a
    test run.

    :return: an empty string
    :rtype: str
    """
    return ''


def _empty_json(*_args, **_kwargs):
    """
    Return an empty JSON-RPC response

    Stands in for `xbmc.executeJSONRPC`.

    :return: an empty JSON object
    :rtype: str
    """
    return '{}'


def _no_op(*_args, **_kwargs):
    """
    Do nothing

    Stands in for the side effect free calls of the `xbmc*` modules, such as
    `xbmc.sleep`.
    """


def _always_false(*_args, **_kwargs):
    """
    Return False

    Stands in for the feature queries of the `xbmc*` modules, which are all
    answered negatively in a test run.

    :return: always False
    :rtype: bool
    """
    return False


def _listdir(path):
    """
    List a directory the way `xbmcvfs.listdir` does

    :param path: path of the directory to list
    :type path: str
    :return: the directory entries as (files, directories) tuple
    :rtype: tuple
    """
    entries = os.listdir(path)
    directories = tuple(entry for entry in entries if os.path.isdir(os.path.join(path, entry)))
    files = tuple(entry for entry in entries if entry not in directories)
    return files, directories


def _makedirs_exist_ok(path):
    """
    Create a directory and its parents, ignoring an existing directory

    :param path: path of the directory to create
    :type path: str
    """
    os.makedirs(path, exist_ok=True)


def _open_file(filepath, mode='r'):
    """
    Open a file, as `xbmcvfs.File` does

    Binary modes are used by `resources.lib.common.fileops` for the database and
    the cookie jar, and `open` rejects an encoding there, so the binary branch
    carries an inline disable of `unspecified-encoding`.

    :param filepath: path of the file to open
    :type filepath: str
    :param mode: mode to open the file with
    :type mode: str
    :return: the open file handle
    :rtype: io.IOBase
    """
    # pylint: disable=consider-using-with
    if 'b' in mode:
        return open(filepath, mode)  # pylint: disable=unspecified-encoding
    return open(filepath, mode, encoding='utf-8')


def _build_xbmc():
    """
    Create the stub of the xbmc module

    :return: the xbmc stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmc')
    for name, level in LOG_LEVELS.items():
        setattr(module, name, level)
    module.Monitor = Monitor
    module.Player = Player
    module.PlayerBusy = type('PlayerBusy', (Exception,), {})
    module.InfoTagVideo = InfoTagVideo
    module.InfoTagMusic = InfoTagMusic
    module.InfoTagPlayer = InfoTagPlayer
    module.VideoStreamDetail = StreamDetail
    module.AudioStreamDetail = StreamDetail
    module.SubtitleStreamDetail = StreamDetail
    module.Actor = Actor
    # The language formats are evaluated as default argument values while the
    # production modules are imported (resources/lib/common/kodi_ops.py:179)
    module.ISO_639_1 = 0
    module.ISO_639_2 = 1
    module.ISO_639_3 = 2
    module.log = _log
    module.sleep = _no_op
    module.getCondVisibility = bool
    module.getInfoLabel = _empty_string
    module.getInfoImage = _empty_string
    module.executebuiltin = _no_op
    module.translatePath = _identity
    module.executeJSONRPC = _empty_json
    module.getRegion = _empty_string
    module.getLanguage = _empty_string
    return module


def _build_xbmcaddon():
    """
    Create the stub of the xbmcaddon module

    :return: the xbmcaddon stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmcaddon')
    module.Addon = Addon
    return module


def _build_xbmcgui():
    """
    Create the stub of the xbmcgui module

    :return: the xbmcgui stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmcgui')
    module.Window = Window
    module.ListItem = ListItem
    module.Dialog = Dialog
    module.DialogProgress = DialogProgress
    module.DialogProgressBG = DialogProgressBG
    module.WindowXMLDialog = WindowXMLDialog
    module.getScreenWidth = lambda: 1920
    module.getScreenHeight = lambda: 1080
    module.getCurrentWindowId = lambda: 0
    module.getCurrentWindowDialogId = lambda: 0
    module.getCurrentChannelId = lambda: 0
    module.NOTIFICATION_INFO = 'info'
    module.NOTIFICATION_WARNING = 'warning'
    module.NOTIFICATION_ERROR = 'error'
    module.ALPHANUM_HIDE_INPUT = 1
    module.INPUT_TYPE_NUMBER = 2
    module.INPUT_ALPHANUM = 0
    module.INPUT_NUMERIC = 2
    module.DLG_YESNO_YES_BTN = 10
    module.DLG_YESNO_NO_BTN = 11
    module.CONTROL_LABEL = 10
    module.CONTROL_BUTTON = 20
    module.CONTROL_LIST = 50
    return module


def _build_xbmcplugin():
    """
    Create the stub of the xbmcplugin module

    :return: the xbmcplugin stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmcplugin')
    module.addDirectoryItems = lambda handle, items, totalItems=0: None
    module.addSortMethod = lambda handle, sortMethod, label2Mask='': None
    module.endOfDirectory = lambda handle, succeeded=True, updateListing=False, cacheToDisc=True: None
    module.setContent = lambda handle, content: None
    module.setPluginCategory = lambda handle, category: None
    module.setResolvedUrl = lambda handle, succeeded, listitem: None
    module.addDirectoryItem = lambda handle, url, listitem, isFolder=False, totalItems=0: None
    module.SORT_METHOD_NONE = 0
    module.SORT_METHOD_LABEL = 1
    module.SORT_METHOD_LABEL_IGNORE_FOLDERS = 2
    module.SORT_METHOD_VIDEO_TITLE = 9
    module.SORT_METHOD_EPISODE = 23
    return module


def _build_xbmcvfs():
    """
    Create the stub of the xbmcvfs module

    :return: the xbmcvfs stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmcvfs')
    module.translatePath = _identity
    module.validatePath = _identity
    module.makeLegalFilename = _identity
    module.exists = os.path.exists
    module.listdir = _listdir
    module.mkdir = os.makedirs
    module.mkdirs = _makedirs_exist_ok
    module.rmdir = _no_op
    module.delete = _no_op
    module.copy = _no_op
    module.rename = _no_op
    module.existsSMB = _always_false
    module.File = _open_file  # noqa: SIM115 pylint: disable=consider-using-with
    return module


def _build_xbmcdrm():
    """
    Create the stub of the xbmcdrm module

    :return: the xbmcdrm stub
    :rtype: types.ModuleType
    """
    module = _new_module('xbmcdrm')
    module.supportsDRM = _always_false
    return module


#: Factories of the stubbed modules, indexed by module name
BUILDERS = {
    'xbmc': _build_xbmc,
    'xbmcaddon': _build_xbmcaddon,
    'xbmcgui': _build_xbmcgui,
    'xbmcplugin': _build_xbmcplugin,
    'xbmcvfs': _build_xbmcvfs,
    'xbmcdrm': _build_xbmcdrm,
}


def _ensure_tests_dir_on_path():
    """
    Make the runtime scripts of the add-on importable

    `resources.lib.common.ipc` imports `AddonSignals` as a top-level module. The
    module lives in `tests/`, which is not on the import path.
    """
    if TESTS_DIR not in sys.path:
        sys.path.insert(0, TESTS_DIR)


def install():
    """
    Register the Kodi stubs in sys.modules

    The function is idempotent, as pytest imports the conftest and the test
    modules more than once.
    """
    _ensure_tests_dir_on_path()
    if 'xbmc' in sys.modules:
        return
    for name, builder in BUILDERS.items():
        sys.modules[name] = builder()
