#!/usr/bin/env python3
import os
import mmap
import ctypes
libc = ctypes.CDLL("libc.so.6")

def pyncc(filen):
    '''Behaves like "no-cache-cat" (ncc) but in pure-python. Only works in GNU/Linux,
    as os.OS_DIRECT is a mirror of a GNU extension.'''
    # May not actually work; experimental.
    f = 0
    os.sync()
    try:
        # os.O_DIRECT *should* mean "read directly from disc, bypassing cache",
        # but comes with a lot of bizzarre baggage regarding precise memory buffer
        # lengths and boundaries. Hopefully this is ameliorated by using os.O_RDONLY,
        # but this incurs an additional gotcha on mmap, below.
        f = os.open(filen, os.O_DIRECT | os.O_SYNC)
        # posix_fadvise asks the kernel to cache the file according to "advice".
        # In this case, passing "4" means "DONTNEED", or "Don't cache".
        libc.posix_fadvise(f,0,0,4)
        # mmap.mmap by default opens in rw mode, but because of O_RDONLY above
        # this triggers a PermissionError. So, must use the mmap.PROT_READ
        # flag to open in read-only mode.
        with mmap.mmap(f, 0, prot=mmap.PROT_READ) as m:
            fc = m.read()
    except Exception as E:
        print("Exception attempting to open file with pyncc:",E,file=sys.stderr)
        sys.exit(1)
    finally:
        # f is positive if successfully opened.
        if f > 0: os.close(f)
    return fc.split(b"\0",1)[0]

if __name__ == "__main__":
    import sys
    print(pyncc(sys.argv[1]))
