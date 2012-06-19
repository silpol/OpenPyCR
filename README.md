#OpenPyCR

##What
A simple Python 3 library/client for controlling and monitoring OpenPCR.
##Why
The official OpenPCR client is written in Adobe Air, which is no longer supported on
Linux and isn't an Open Source platform in any case.
Also, Python 3 is an easier language to develop further, making it more likely that
others will extend this work to make OpenPCR even better.

##Where
Immediate needs for this client include code to make it fully cross-platform. The
ncc binaries that allow reading of machine state are compiled for Windows and Linux,
presumably the Linux binaries are also used for Mac. All that should be needed to
make this cross-platform is to amend openpcrlib with default mount directories for
OpenPCR. I (Cathal) have no intention of doing so, as I only use/endorse Linux.
It may also be necessary to identify Linux distros other than Ubuntu if they have
different mountpoints to the Ubuntu default (/media/OPENPCR).

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

##How
###Usage
openpycr [option] <args..>\nOptions:
* status - Print a one-time status report to stdout
* monitor - Open a curses monitor for OpenPCR device
* sendstring <string> - Send a program string to the device
* sendprogram <file> - Upload a program from flat text file or stdin (use '-') to the device
* stop - Send a stop signal to the device
* log <interval> <file> - Append csv-formatted log data every <interval> seconds to a file or stdout (use '-')
* proghelp - Print information on how to format programs.

###Technical
OpenPCR uses an unconventional PC:Device interface; when connected, it mounts what
appears to be a (very small) mass storage device called "OPENPCR". Two files in
particular are relevant here; "CONTROL.TXT" and "STATUS.TXT"
To upload new programs, one simply writes/overwrites "CONTROL.TXT" with the new
program. To read the status of the device, one fetches the contents of "STATUS.TXT".

However, some level of system cachine prevents repeated reading of STATUS.TXT,
yielding the same answer as the first read every time thereafter. Extensive
experimentation and documentation-scanning in Python 3 was fruitless in finding a
means to avoid this problem, and so this program currently relies on the "No Cache
Cat" binaries from the original OpenPCR distribution. A native python solution would
be very welcome, if only to satisfy my curiousity.
