"""Windows shim for the OpenTimestamps client: python-bitcoinlib looks for
OpenSSL via ctypes.util.find_library, which returns None on Windows. Python
itself ships libssl-3/libcrypto-3 in its DLLs folder - point the lookup there,
then hand off to the real ots CLI."""
import ctypes.util
import os
import sys

_dlls = os.path.join(sys.base_prefix, "DLLs")
_orig = ctypes.util.find_library

def _patched(name):
    r = _orig(name)
    if r:
        return r
    n = (name or "").lower()
    if "ssl" in n:
        # python-bitcoinlib asks for 'ssl' but uses BN_/EC_ symbols, which
        # live in libcrypto - hand it that instead
        p = os.path.join(_dlls, "libcrypto-3.dll")
        return p if os.path.exists(p) else r
    if "crypto" in n or "eay" in n:
        p = os.path.join(_dlls, "libcrypto-3.dll")
        return p if os.path.exists(p) else r
    return r

ctypes.util.find_library = _patched
# libssl-3 needs libcrypto-3 loadable from the same dir
os.add_dll_directory(_dlls)
ctypes.CDLL(os.path.join(_dlls, "libcrypto-3.dll"))

from otsclient.ots import main  # noqa: E402

if __name__ == "__main__":
    main()
