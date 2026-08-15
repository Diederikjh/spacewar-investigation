#!/usr/bin/env python3

"""Activate one exact X11 window, verify focus, then optionally send input."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import sys
import time


SUBSTRUCTURE_NOTIFY_MASK = 1 << 19
SUBSTRUCTURE_REDIRECT_MASK = 1 << 20
CLIENT_MESSAGE = 33
CURRENT_TIME = 0
REVERT_TO_PARENT = 2


class ClientMessageData(ctypes.Union):
    _fields_ = [
        ("bytes", ctypes.c_char * 20),
        ("shorts", ctypes.c_short * 10),
        ("longs", ctypes.c_long * 5),
    ]


class ClientMessageEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ClientMessageData),
    ]


class XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("client", ClientMessageEvent),
        ("padding", ctypes.c_long * 24),
    ]


class XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resource_id", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


XErrorHandler = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(XErrorEvent)
)


def parse_window_id(value: str) -> int:
    try:
        window = int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("WINDOW_ID must be decimal or 0x-prefixed hex") from error
    if window <= 0:
        raise argparse.ArgumentTypeError("WINDOW_ID must be positive")
    return window


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Activate and focus one exact X11 window before sending any synthetic input. "
            "The command fails without emitting keys if focus cannot be verified."
        )
    )
    result.add_argument("window_id", type=parse_window_id)
    subparsers = result.add_subparsers(dest="action", required=True)
    subparsers.add_parser("focus", help="activate the window and verify focus only")

    key_parser = subparsers.add_parser("key", help="send one named X11 key")
    key_parser.add_argument("key")

    hotkey_parser = subparsers.add_parser("hotkey", help="send a modifier and key")
    hotkey_parser.add_argument("modifier")
    hotkey_parser.add_argument("key")

    text_parser = subparsers.add_parser(
        "text", help="type ASCII text without pressing Return"
    )
    text_parser.add_argument("text")
    return result


class X11Input:
    def __init__(self) -> None:
        x11_name = ctypes.util.find_library("X11")
        xtst_name = ctypes.util.find_library("Xtst")
        if not x11_name or not xtst_name:
            raise RuntimeError("required X11 input libraries are unavailable")

        self.x11 = ctypes.CDLL(x11_name)
        self.xtst = ctypes.CDLL(xtst_name)
        self._declare_functions()
        self.last_x_error: tuple[int, int, int] | None = None
        self.error_handler = XErrorHandler(self._record_x_error)
        self.x11.XSetErrorHandler(self.error_handler)
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("cannot open the active X11 display")
        self.root = self.x11.XDefaultRootWindow(self.display)

    def _declare_functions(self) -> None:
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x11.XQueryTree.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self.x11.XQueryTree.restype = ctypes.c_int
        self.x11.XSetErrorHandler.argtypes = [XErrorHandler]
        self.x11.XSetErrorHandler.restype = ctypes.c_void_p
        self.x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.x11.XInternAtom.restype = ctypes.c_ulong
        self.x11.XSendEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_long,
            ctypes.POINTER(XEvent),
        ]
        self.x11.XSendEvent.restype = ctypes.c_int
        self.x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XRaiseWindow.restype = ctypes.c_int
        self.x11.XSetInputFocus.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self.x11.XSetInputFocus.restype = ctypes.c_int
        self.x11.XGetInputFocus.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.x11.XGetInputFocus.restype = ctypes.c_int
        self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x11.XKeysymToKeycode.restype = ctypes.c_uint
        self.x11.XFlush.argtypes = [ctypes.c_void_p]
        self.x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x11.XFree.argtypes = [ctypes.c_void_p]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xtst.XTestFakeKeyEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self.xtst.XTestFakeKeyEvent.restype = ctypes.c_int

    def _record_x_error(
        self, _display: ctypes.c_void_p, event: ctypes.POINTER(XErrorEvent)
    ) -> int:
        details = event.contents
        self.last_x_error = (
            details.error_code,
            details.request_code,
            details.resource_id,
        )
        return 0

    def sync_checked(self, context: str) -> None:
        self.x11.XSync(self.display, 0)
        if self.last_x_error is not None:
            error_code, request_code, resource_id = self.last_x_error
            self.last_x_error = None
            raise RuntimeError(
                f"{context}: X11 error {error_code} on request {request_code} "
                f"for 0x{resource_id:x}"
            )

    def close(self) -> None:
        self.x11.XCloseDisplay(self.display)

    def parent(self, window: int) -> tuple[int, int]:
        self.last_x_error = None
        root = ctypes.c_ulong()
        parent = ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        count = ctypes.c_uint()
        status = self.x11.XQueryTree(
            self.display,
            window,
            ctypes.byref(root),
            ctypes.byref(parent),
            ctypes.byref(children),
            ctypes.byref(count),
        )
        if children:
            self.x11.XFree(children)
        self.sync_checked(f"X11 window 0x{window:x} is unavailable")
        if not status:
            raise RuntimeError(f"X11 window 0x{window:x} does not exist")
        return root.value, parent.value

    def frame(self, target: int) -> int:
        window = target
        for _ in range(64):
            root, parent = self.parent(window)
            if parent == root:
                return window
            if not parent or parent == window:
                break
            window = parent
        raise RuntimeError(f"cannot resolve the top-level frame for 0x{target:x}")

    def activate_and_focus(self, target: int) -> None:
        frame = self.frame(target)
        active_atom = self.x11.XInternAtom(self.display, b"_NET_ACTIVE_WINDOW", 0)
        event = XEvent()
        event.client.type = CLIENT_MESSAGE
        event.client.window = target
        event.client.message_type = active_atom
        event.client.format = 32
        event.client.data.longs[0] = 1
        event.client.data.longs[1] = CURRENT_TIME

        self.x11.XRaiseWindow(self.display, frame)
        sent = self.x11.XSendEvent(
            self.display,
            self.root,
            0,
            SUBSTRUCTURE_REDIRECT_MASK | SUBSTRUCTURE_NOTIFY_MASK,
            ctypes.byref(event),
        )
        if not sent:
            raise RuntimeError(f"window manager rejected activation for 0x{target:x}")
        self.x11.XFlush(self.display)
        time.sleep(0.25)

        self.x11.XSetInputFocus(
            self.display, target, REVERT_TO_PARENT, CURRENT_TIME
        )
        self.x11.XRaiseWindow(self.display, frame)
        self.sync_checked(f"cannot focus X11 window 0x{target:x}")
        time.sleep(0.1)

        focused = ctypes.c_ulong()
        revert = ctypes.c_int()
        self.x11.XGetInputFocus(
            self.display, ctypes.byref(focused), ctypes.byref(revert)
        )
        if focused.value != target:
            raise RuntimeError(
                f"focus verification failed: requested 0x{target:x}, got 0x{focused.value:x}"
            )

    def emit(self, name: str, pressed: bool) -> None:
        keysym = self.x11.XStringToKeysym(name.encode("ascii"))
        if not keysym:
            raise RuntimeError(f"unknown X11 key name: {name}")
        keycode = self.x11.XKeysymToKeycode(self.display, keysym)
        if not keycode:
            raise RuntimeError(f"unmapped X11 key name: {name}")
        if not self.xtst.XTestFakeKeyEvent(
            self.display, keycode, int(pressed), CURRENT_TIME
        ):
            raise RuntimeError(f"failed to emit X11 key: {name}")
        self.x11.XFlush(self.display)
        time.sleep(0.025)

    def tap(self, name: str, shifted: bool = False) -> None:
        if shifted:
            self.emit("Shift_L", True)
        self.emit(name, True)
        self.emit(name, False)
        if shifted:
            self.emit("Shift_L", False)

    def type_text(self, value: str) -> None:
        special = {
            " ": ("space", False),
            ":": ("semicolon", True),
            "-": ("minus", False),
            "_": ("minus", True),
            ".": ("period", False),
            "/": ("slash", False),
            "\\": ("backslash", False),
        }
        for character in value:
            if ord(character) >= 128:
                raise RuntimeError("text input is limited to ASCII")
            if character in special:
                self.tap(*special[character])
            elif character.isalpha():
                self.tap(character.lower(), character.isupper())
            elif character.isdigit():
                self.tap(character)
            else:
                raise RuntimeError(f"unsupported text character: {character!r}")


def main() -> int:
    arguments = parser().parse_args()
    xinput = X11Input()
    try:
        xinput.activate_and_focus(arguments.window_id)
        if arguments.action == "key":
            xinput.tap(arguments.key)
        elif arguments.action == "hotkey":
            xinput.emit(arguments.modifier, True)
            try:
                xinput.tap(arguments.key)
            finally:
                xinput.emit(arguments.modifier, False)
        elif arguments.action == "text":
            xinput.type_text(arguments.text)
        print(f"focused 0x{arguments.window_id:x}; action {arguments.action} completed")
        return 0
    finally:
        xinput.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
