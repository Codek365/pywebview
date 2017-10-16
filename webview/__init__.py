#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
pywebview is a lightweight cross-platform wrapper around a webview component that allows to display HTML content in its
own dedicated window. Works on Windows, OS X and Linux and compatible with Python 2 and 3.

(C) 2014-2016 Roman Sirokov and contributors
Licensed under BSD license

http://github.com/r0x0r/pywebview/
"""


import platform
import os
import sys
import re
import logging
from threading import Event, current_thread
from uuid import uuid4

from .localization import localization

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

OPEN_DIALOG = 10
FOLDER_DIALOG = 20
SAVE_DIALOG = 30


class Config (dict):

    def __init__(self):
        self.use_qt = "USE_QT" in os.environ
        self.use_win32 = "USE_WIN32" in os.environ

    def __getitem__(self, key):
        return getattr(self, key.lower())

    def __setitem__(self, key, value):
        setattr(self, key.lower(), value)


config = Config()

_initialized = False
_webview_ready = Event()


def _initialize_imports():
    global _initialized, gui
    import_error = False

    if not _initialized:
        if platform.system() == "Darwin":
            if not config.use_qt:
                try:
                    import webview.cocoa as gui
                except ImportError:
                    logger.exception("PyObjC cannot be loaded")
                    import_error = True

            if import_error or config.use_qt:
                try:
                    import webview.qt as gui
                    logger.debug("Using QT")
                except ImportError as e:
                    # Panic
                    logger.exception("QT cannot be loaded")
                    raise Exception("You must have either PyObjC (for Cocoa support) or Qt with Python bindings installed in order to use this library.")

        elif platform.system() == "Linux":
            if not config.use_qt:
                try:
                    import webview.gtk as gui
                    logger.debug("Using GTK")
                except (ImportError, ValueError) as e:
                    logger.exception("GTK cannot be loaded")
                    import_error = True

            if import_error or config.use_qt:
                try:
                    # If GTK is not found, then try QT
                    import webview.qt as gui
                    logger.debug("Using QT")
                except ImportError as e:
                    # Panic
                    logger.exception("QT cannot be loaded")
                    raise Exception("You must have either QT or GTK with Python extensions installed in order to use this library.")

        elif platform.system() == "Windows":
            #Try .NET first unless use_win32 flag is set
            if not config.use_win32:
                try:
                    import webview.winforms as gui
                    logger.debug("Using .NET")
                except ImportError as e:
                    logger.exception("pythonnet cannot be loaded")
                    import_error = True


            if import_error or config.use_win32:
                try:
                    # If .NET is not found, then try Win32
                    import webview.win32 as gui
                    logger.debug("Using Win32")
                except ImportError as e:
                    # Panic
                    logger.exception("PyWin32 cannot be loaded")
                    raise Exception("You must have either pythonnet or pywin32 installed in order to use this library.")
        else:
            raise Exception("Unsupported platform. Only Windows, Linux and OS X are supported.")

        _initialized = True


def create_file_dialog(dialog_type=OPEN_DIALOG, directory='', allow_multiple=False, save_filename=''):
    """
    Create a file dialog
    :param dialog_type: Dialog type: open file (OPEN_DIALOG), save file (SAVE_DIALOG), open folder (OPEN_FOLDER). Default
                        is open file.
    :param directory: Initial directory
    :param allow_multiple: Allow multiple selection. Default is false.
    :param save_filename: Default filename for save file dialog.
    :return:
    """

    if not os.path.exists(directory):
        directory = ''

    try:
        _webview_ready.wait(5)
        return gui.create_file_dialog(dialog_type, directory, allow_multiple, save_filename)
    except NameError as e:
        raise Exception("Create a web view window first, before invoking this function")


def load_url(url, uid='master'):
    """
    Load a new URL into a previously created WebView window. This function must be invoked after WebView windows is
    created with create_window(). Otherwise an exception is thrown.
    :param url: url to load
    :param uid: uid of the target instance
    """
    try:
        _webview_ready.wait(5)
        gui.load_url(url, uid)
    except NameError:
        raise Exception("Create a web view window first, before invoking this function")


def load_html(content, base_uri='', uid='master'):
    """
    Load a new content into a previously created WebView window. This function must be invoked after WebView windows is
    created with create_window(). Otherwise an exception is thrown.
    :param content: Content to load.
    :param base_uri: Base URI for resolving links. Default is "".
    :param uid: uid of the target instance
    """
    try:
        _webview_ready.wait(5)
        gui.load_html(_make_unicode(content), base_uri, uid)
    except NameError as e:
        raise Exception("Create a web view window first, before invoking this function")


def create_window(title, url=None, width=800, height=600,
                  resizable=True, fullscreen=False, min_size=(200, 100), strings={}, confirm_quit=False,
                  background_color='#FFFFFF'):
    """
    Create a web view window using a native GUI. The execution blocks after this function is invoked, so other
    program logic must be executed in a separate thread.
    :param title: Window title
    :param url: URL to load
    :param width: Optional window width (default: 800px)
    :param height: Optional window height (default: 600px)
    :param resizable True if window can be resized, False otherwise. Default is True
    :param fullscreen: True if start in fullscreen mode. Default is False
    :param min_size: a (width, height) tuple that specifies a minimum window size. Default is 200x100
    :param strings: a dictionary with localized strings
    :param confirm_quit: Display a quit confirmation dialog. Default is False
    :param background_color: Background color as a hex string that is displayed before the content of webview is loaded. Default is white.
    :return:
    """
    uid = 'webview' + uuid4().hex

    valid_color = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
    if not re.match(valid_color, background_color):
        raise ValueError('{0} is not a valid hex triplet color'.format(background_color))

    if not _initialized:
        # Check if starting up from main thread; if not, wait; finally raise exception
        if current_thread().name != 'MainThread':
            if _webview_ready.wait(5) != True:
                raise Exception("Call create_window from the main thread first, and then from subthreads")
        else:
            _initialize_imports()
            localization.update(strings)
            uid = 'master'

    _webview_ready.clear()
    gui.create_window(uid, _make_unicode(title), _transform_url(url),
                      width, height, resizable, fullscreen, min_size, confirm_quit,
                      background_color, _webview_ready)
    return uid


def get_current_url(uid='master'):
    """
    Get a current URL
    :param uid: uid of the target instance
    """
    try:
        _webview_ready.wait(5)
        return gui.get_current_url(uid)
    except NameError:
        raise Exception("Create a web view window first, before invoking this function")


def destroy_window(uid='master'):
    """
    Destroy a web view window
    :param uid: uid of the target instance
    """
    try:
        _webview_ready.wait(5)
        gui.destroy_window(uid)
    except NameError:
        raise Exception("Create a web view window first, before invoking this function")


def toggle_fullscreen(uid='master'):
    """
    Toggle fullscreen mode
    :param uid: uid of the target instance
    """
    try:
        _webview_ready.wait(5)
        gui.toggle_fullscreen(uid)
    except NameError:
        raise Exception("Create a web view window first, before invoking this function")


def evaluate_js(script, uid='master'):
    """
    Evaluate given JavaScript code and return the result
    :param script: The JavaScript code to be evaluated
    :param uid: uid of the target instance
    :return: Return value of the evaluated code
    """
    try:
        _webview_ready.wait(5)
        return gui.evaluate_js(script, uid)
    except NameError:
        raise Exception("Create a web view window first, before invoking this function")


def _get_item(list_, attr, value):
    """
    Return the first item from a :list_ of objects whose :attr-ibute matches :value
    attr should be a string. An exception is thrown if no match is found.
    """
    for i in list_:
        try:
            if getattr(i, attr) == value:
                return i
        except AttributeError:
            break

    raise Exception("No object found with '{0}' '{1}'".format(attr, value))


def _escape_string(string):
    return string.replace('"', r'\"').replace('\n', r'\n')


def _make_unicode(string):
    """
    Python 2 and 3 compatibility function that converts a string to Unicode. In case of Unicode, the string is returned
    unchanged
    :param string: input string
    :return: Unicode string
    """
    if sys.version < '3' and isinstance(string, str):
        return unicode(string.decode('utf-8'))

    return string


def _transform_url(url):
    if url == None:
        return url
    if url.find(":") == -1:
        return 'file://' + os.path.abspath(url)
    else:
        return url
