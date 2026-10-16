"""Keep recovery gentle on the computer.

Recovery runs for hours on old, sometimes failing, disks. These helpers make it a good
background citizen:

- low_priority(): workers get idle CPU, very-low disk and low memory priority; the window
  gets below-normal CPU and low disk priority, so the OS serves everything else first.
- free_ram_gb(): the dispatcher waits when free RAM is low instead of pushing the OS into
  paging to disk.
- use_temp_dir(): temp files go to the configured folder (keep it on a healthy disk).
"""
import ctypes, os, tempfile

_IDLE = 0x00000040
_BELOW_NORMAL = 0x00004000
_PROCESS_IO_PRIORITY = 33       # NtSetInformationProcess class
_PROCESS_MEMORY_PRIORITY = 0    # SetProcessInformation class


def low_priority(background=False):
    if os.name != "nt":
        try: os.nice(10)
        except Exception: pass
        return
    k, nt = ctypes.windll.kernel32, ctypes.windll.ntdll
    # declare types: without them the 64-bit process handle is truncated and calls silently fail
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k.SetProcessInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    nt.NtSetInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    h = k.GetCurrentProcess()
    ok = bool(k.SetPriorityClass(h, _IDLE if background else _BELOW_NORMAL))
    io = ctypes.c_ulong(0 if background else 1)  # 0 = very low, 1 = low disk priority
    ok &= nt.NtSetInformationProcess(h, _PROCESS_IO_PRIORITY, ctypes.byref(io), 4) == 0
    if background:
        mem = ctypes.c_ulong(2)  # MEMORY_PRIORITY_LOW: our pages are first to go, others' stay in RAM
        ok &= bool(k.SetProcessInformation(h, _PROCESS_MEMORY_PRIORITY, ctypes.byref(mem), 4))
    return ok


def current_priorities():
    """(cpu class, disk priority, memory priority) of this process, for checks (Windows)."""
    if os.name != "nt":
        return ("nice", os.nice(0), None)
    k, nt = ctypes.windll.kernel32, ctypes.windll.ntdll
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.GetPriorityClass.argtypes = [ctypes.c_void_p]
    k.GetProcessInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    nt.NtQueryInformationProcess.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    h = k.GetCurrentProcess()
    io, mem = ctypes.c_ulong(), ctypes.c_ulong()
    nt.NtQueryInformationProcess(h, _PROCESS_IO_PRIORITY, ctypes.byref(io), 4, None)
    k.GetProcessInformation(h, _PROCESS_MEMORY_PRIORITY, ctypes.byref(mem), 4)
    cls = {0x40: "idle", 0x4000: "below normal", 0x20: "normal"}.get(k.GetPriorityClass(h), "other")
    return cls, ["very low", "low", "normal", "high"][io.value] if io.value < 4 else io.value, mem.value


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def free_ram_gb():
    if os.name != "nt":
        try:
            return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2 ** 30
        except (ValueError, OSError, AttributeError):
            return 99.0
    st = _MemStatus(); st.dwLength = ctypes.sizeof(_MemStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / 2 ** 30


def use_temp_dir(path):
    d = os.path.abspath(path)
    os.makedirs(d, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = d
    tempfile.tempdir = d
    return d
