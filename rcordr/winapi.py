"""Utilidades Win32 vía ctypes (sin dependencias extra)."""

import ctypes
import io
import struct
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- Tipos de retorno correctos para 64 bits -------------------------------
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]

ERROR_ALREADY_EXISTS = 183
GMEM_MOVEABLE = 0x0002
CF_DIB = 8
CF_HDROP = 15
WDA_EXCLUDEFROMCAPTURE = 0x11


def set_dpi_aware() -> None:
    """Coordenadas en píxeles físicos, iguales a las que usa mss/ffmpeg."""
    try:
        # PER_MONITOR_AWARE_V2
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            user32.SetProcessDPIAware()


def work_area() -> tuple[int, int, int, int]:
    """Área útil del monitor principal (sin la barra de tareas)."""
    rect = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


def cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


_mutex = None


def single_instance(name: str) -> bool:
    """Devuelve False si ya hay otra instancia ejecutándose."""
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, f"Local\\{name}_single_instance")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def exclude_from_capture(tk_window) -> None:
    """Oculta una ventana Tk en capturas/grabaciones (Windows 10 2004+)."""
    try:
        tk_window.update_idletasks()
        hwnd = user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()
        user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
    except OSError:
        pass


def click_through(tk_window) -> None:
    """Hace que los clics atraviesen la ventana (y la quita de Alt+Tab)."""
    tk_window.update_idletasks()
    hwnd = user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()
    GWL_EXSTYLE = -20
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    # WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x80000 | 0x20 | 0x80)


def copy_image_to_clipboard(image) -> bool:
    """Copia una imagen PIL al portapapeles de Windows (formato CF_DIB)."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "BMP")
    return _set_clipboard(CF_DIB, buf.getvalue()[14:])  # sin BITMAPFILEHEADER


def copy_file_to_clipboard(path: str) -> bool:
    """Copia un archivo al portapapeles (como Ctrl+C en el Explorador).

    Así el vídeo se puede pegar con Ctrl+V en WhatsApp Desktop/Web.
    """
    # DROPFILES: pFiles=20, pt=(0,0), fNC=0, fWide=1, después rutas UTF-16
    header = struct.pack("<IiiII", 20, 0, 0, 0, 1)
    files = (str(path) + "\0\0").encode("utf-16-le")
    return _set_clipboard(CF_HDROP, header + files)


def _set_clipboard(fmt: int, data: bytes) -> bool:
    for _ in range(10):  # otra app puede tener el portapapeles abierto
        if user32.OpenClipboard(None):
            break
        kernel32.Sleep(20)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(fmt, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()
