"""Minimal ctypes bindings for the Win32 calls used by this utility.

Using ctypes keeps the tool dependency free: it runs on a stock CPython
installation without pywin32.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

if sys.platform != "win32":
    raise ImportError("opacity_control.windows requires Windows.")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

HWND = wintypes.HWND
DWORD = wintypes.DWORD
BOOL = wintypes.BOOL
UINT = wintypes.UINT
LONG = wintypes.LONG
WPARAM = wintypes.WPARAM
LPARAM = wintypes.LPARAM
HANDLE = wintypes.HANDLE
RECT = wintypes.RECT
MSG = wintypes.MSG
LPRECT = ctypes.POINTER(RECT)
POINTER_DWORD = ctypes.POINTER(DWORD)

# Window style
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Layered window attributes
LWA_ALPHA = 0x00000002

# SetWindowPos
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

# Window relationships
GW_OWNER = 4

# WinEvent
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# Hotkeys
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
VK_ESCAPE = 0x1B

# DWM
DWMWA_CLOAKED = 14

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

WNDENUMPROC = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None, HANDLE, DWORD, HWND, LONG, LONG, DWORD, DWORD
)


def _configure() -> None:
    user32.EnumWindows.argtypes = (WNDENUMPROC, LPARAM)
    user32.EnumWindows.restype = BOOL

    user32.IsWindow.argtypes = (HWND,)
    user32.IsWindow.restype = BOOL
    user32.IsWindowVisible.argtypes = (HWND,)
    user32.IsWindowVisible.restype = BOOL
    user32.IsIconic.argtypes = (HWND,)
    user32.IsIconic.restype = BOOL
    user32.IsZoomed.argtypes = (HWND,)
    user32.IsZoomed.restype = BOOL

    user32.GetWindowTextLengthW.argtypes = (HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = (HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int

    user32.GetWindowThreadProcessId.argtypes = (HWND, POINTER_DWORD)
    user32.GetWindowThreadProcessId.restype = DWORD
    user32.GetWindow.argtypes = (HWND, UINT)
    user32.GetWindow.restype = HWND
    user32.GetForegroundWindow.restype = HWND

    user32.GetWindowRect.argtypes = (HWND, LPRECT)
    user32.GetWindowRect.restype = BOOL
    user32.SetWindowPos.argtypes = (
        HWND,
        HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        UINT,
    )
    user32.SetWindowPos.restype = BOOL

    user32.SetLayeredWindowAttributes.argtypes = (
        HWND,
        wintypes.COLORREF,
        wintypes.BYTE,
        DWORD,
    )
    user32.SetLayeredWindowAttributes.restype = BOOL
    user32.GetLayeredWindowAttributes.argtypes = (
        HWND,
        POINTER_DWORD,
        ctypes.POINTER(wintypes.BYTE),
        POINTER_DWORD,
    )
    user32.GetLayeredWindowAttributes.restype = BOOL

    long_ptr = ctypes.c_ssize_t
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.GetWindowLongPtrW.argtypes = (HWND, ctypes.c_int)
        user32.GetWindowLongPtrW.restype = long_ptr
        user32.SetWindowLongPtrW.argtypes = (HWND, ctypes.c_int, long_ptr)
        user32.SetWindowLongPtrW.restype = long_ptr
    else:
        user32.GetWindowLongW.argtypes = (HWND, ctypes.c_int)
        user32.GetWindowLongW.restype = wintypes.LONG
        user32.SetWindowLongW.argtypes = (HWND, ctypes.c_int, wintypes.LONG)
        user32.SetWindowLongW.restype = wintypes.LONG

    user32.SetWinEventHook.argtypes = (
        DWORD,
        DWORD,
        wintypes.HMODULE,
        WINEVENTPROC,
        DWORD,
        DWORD,
        DWORD,
    )
    user32.SetWinEventHook.restype = HANDLE
    user32.UnhookWinEvent.argtypes = (HANDLE,)
    user32.UnhookWinEvent.restype = BOOL

    user32.RegisterHotKey.argtypes = (HWND, ctypes.c_int, UINT, UINT)
    user32.RegisterHotKey.restype = BOOL
    user32.UnregisterHotKey.argtypes = (HWND, ctypes.c_int)
    user32.UnregisterHotKey.restype = BOOL
    user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), HWND, UINT, UINT)
    user32.GetMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = (ctypes.POINTER(MSG),)
    user32.TranslateMessage.restype = BOOL
    user32.DispatchMessageW.argtypes = (ctypes.POINTER(MSG),)
    user32.DispatchMessageW.restype = ctypes.c_ssize_t
    user32.PostThreadMessageW.argtypes = (DWORD, UINT, WPARAM, LPARAM)
    user32.PostThreadMessageW.restype = BOOL

    kernel32.GetCurrentThreadId.restype = DWORD
    kernel32.OpenProcess.argtypes = (DWORD, BOOL, DWORD)
    kernel32.OpenProcess.restype = HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        HANDLE,
        DWORD,
        wintypes.LPWSTR,
        POINTER_DWORD,
    )
    kernel32.QueryFullProcessImageNameW.restype = BOOL
    kernel32.CloseHandle.argtypes = (HANDLE,)
    kernel32.CloseHandle.restype = BOOL

    dwmapi.DwmGetWindowAttribute.argtypes = (
        HWND,
        DWORD,
        ctypes.c_void_p,
        DWORD,
    )
    dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


_configure()

_GET_LONG = getattr(
    user32, "GetWindowLongPtrW", user32.GetWindowLongW
)
_SET_LONG = getattr(
    user32, "SetWindowLongPtrW", user32.SetWindowLongW
)


def is_window(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd))


def is_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def is_minimized(hwnd: int) -> bool:
    return bool(user32.IsIconic(hwnd))


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(hwnd))


def window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def owner_window(hwnd: int) -> int:
    return int(user32.GetWindow(hwnd, GW_OWNER) or 0)


def process_id(hwnd: int) -> int:
    pid = DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def process_name(hwnd: int) -> str:
    pid = process_id(hwnd)
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        ):
            return os.path.basename(buffer.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


def is_cloaked(hwnd: int) -> bool:
    cloaked = DWORD(0)
    result = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_CLOAKED,
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked),
    )
    return result == 0 and cloaked.value != 0


def ex_style(hwnd: int) -> int:
    return int(_GET_LONG(hwnd, GWL_EXSTYLE))


def set_ex_style(hwnd: int, style: int) -> None:
    _SET_LONG(hwnd, GWL_EXSTYLE, style)


def get_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def set_position(hwnd: int, x: int, y: int) -> bool:
    return bool(
        user32.SetWindowPos(
            hwnd,
            0,
            x,
            y,
            0,
            0,
            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
        )
    )


def set_alpha(hwnd: int, alpha: int) -> bool:
    alpha = max(0, min(255, alpha))
    return bool(
        user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
    )


def thread_id() -> int:
    return int(kernel32.GetCurrentThreadId())


def post_quit_message(tid: int) -> bool:
    return bool(user32.PostThreadMessageW(tid, WM_QUIT, 0, 0))
