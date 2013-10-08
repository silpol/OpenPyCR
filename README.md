# OpenPyCR
A pure-python controller and monitor application for the OpenPCR thermal cycler.
by Cathal Garvey, copyright 2013, licensed under the GNU Affero GPL v3 or later.

## What is OpenPyCR?
OpenPyCR is an alternative controller/monitor program for the OpenPCR. The program
provided by the OpenPCR team for the device is based on Adobe Air, a closed-source
and insecure platform, and a platform for which linux support was withdrawn long ago.

While the OpenPCR developers were kind and patient enough to assist me in getting
the Adobe Air application to work correctly on Ubuntu, a better system was needed
for Linux users generally, and there were things I wanted to do that aren't possible
with the normal controller application, too.

## How do I use this?
Right now, OpenPyCR is a terminal application only. To use it, go to the folder
where it was downloaded (it must have openpcrlib.py in the same folder, for now),
and type: 

    python3 openpycr.py --help

for usage information. For more specific help on the subcommands try:

    python3 openpycr (subcommand) --help

OpenPyCR uses a simple format for specifying PCR programs which is 'compiled'
down to the YAML form used by OpenPCR. Programs are written as flat text files
(NOT LibreOffice or (ugh) Microsoft Word files! Use gedit, geany, notepad, etc..),
in a simple format.

Programs begin with "headers", each on a separate line. Headers are colon-separated
key: value pairs. The only two with any meaning right now are "Title" and "Lid".

Then a single blank line is left, to separate headers from program.

The program itself is a partially indented notation you may have used naturally:
"seconds @ temperature description", where you can (and should) follow seconds
with "s" and temperature with "C" for clarity, and where description is text
to display on the OpenPCR screen.

For repetitions, write "x10" on a line, then follow with the steps you want
repeated indented by a consistent amount.

Here's an example program:
```
Title: Canonical PCR
Lid: 95

60s @ 95C Burn In
x35:
    20s @ 95C Denature
    15s @ 65C Anneal
    30s @ 72C Extend
20s @ 4C Chill
``` 

This program can be saved to a file, and then sent to the OpenPCR with:

    python3 openpycr.py send Programs/Sample.pcr

OpenPyCR compiles the above program (included) to the far less readable OpenPCR
format expected by the device firmware:
s=ACGTC&l=95&c=start&n=Canonical PCR&p=([60|95|Burn In])(35[20|95|Denature][15|65|Anneal][30|72|Extend])([20|4|Chill])

## Platform Specificity
This section is somewhat technical; the TLDR version is "OpenPyCR only works
on Linux for monitoring but is probably OK for programming OpenPCRs from lesser
platforms if you know what you're doing".

It turned out while developing OpenPyCR that writing new programs (directing the
device) was trivial, while reading from the device (monitoring, logging, etc.)
was quite hard to achieve due to system level caching.

OpenPCR has an odd control structure. Rather than acting as a serial or USB device,
it masquerades as a mass-storage device, with two key files: STATUS.TXT and CONTROL.TXT.
The former is on the device at power-up time, and can be read from to get the current
state of the OpenPCR device. The latter, if written or overwritten, instructs the
device to follow the contained instructions (in restricted YAML format).

The normal client for OpenPCR makes use of a special application called "ncc" to
read the status of the device, because all major operating systems use disk caches
that assume the status file on the OpenPCR does not vary between reads (which it
does!). Without this ncc application, the system always returns the value it first
read from the device without checking whether its changed.

The ncc binaries are written for Windows, Mac and Linux separately, and must be
compiled for each architecture separately, so users with Raspberry Pi control
boards must recompile ncc for ARM, for example. One goal of OpenPyCR was to do
away with architecture-specific compilation, so OpenPyCR will work on any system
running Linux with Python installed without changes.

OpenPyCR is pure-python, meaning that it requires no specially compiled C++
binaries like the normal client. It instead relies on Linux system calls to
guarantee that disk/file caching will not interfere with reading the status
of the OpenPCR device.

This is clean, cross-architecture, and easy, but it also means that OpenPyCR
cannot read OpenPCR's status without interference on any platform other than
GNU/Linux. This is *not considered a bug*.

Additionally, in case it needs to be said this is written in *modern python*;
you will require Python 3, preferably Python version 3.3, for this to work.
Versions below 3.3 lack the os.posix_fadvise system call that is used to avoid
caching, but a shim operation will be attempted using ctypes nevertheless.

## What Next
Further development of this library/client might head towards a Tcl/Tk GUI, locally-
hosted webapp, or a daemon for smartphone control when connected to a networked PC.

This system could also be extended with relative ease to allow "metaprogramming" of
OpenPCRs, where new cycles are automatically uploaded to the device once it completes
prior cycles. A system such as this could allow programs of much greater complexity
than those currently possible using the one-time-upload paradigm.

Furthermore, outsourcing control to a PC may allow for more interactive or dynamic
programming if feedback is provided to the PC through other means; a turbidity
meter or spectrometer might read samples and adjust cycling parameters, for example,
a prospect unlikely to be achievable with the OpenPCR hardware as-is.
