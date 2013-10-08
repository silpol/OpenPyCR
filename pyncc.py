#!/usr/bin/env python3
import os
import mmap
import sys
if sys.version_info[:2] < (3,3):
    # native posix_fadvise introduced in 3.3, can shim in with ctypes:
    import ctypes
    libc = ctypes.CDLL("libc.so.6")
    os.posix_fadvise = libc.posix_fadvise
    os.POSIX_FADV_NORMAL     = 0
    os.POSIX_FADV_RANDOM     = 1
    os.POSIX_FADV_SEQUENTIAL = 2
    os.POSIX_FADV_WILLNEED   = 3
    os.POSIX_FADV_DONTNEED   = 4
    os.POSIX_FADV_NOREUSE    = 5

if __name__ == "__main__":
    import sys
    with open(sys.argv[1],"rb") as InF:
        os.posix_fadvise(InF.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        print(InF.read().split(b"\0",1)[0].decode())
