#!/usr/bin/env python3
import curses
import time
import sys
import argparse
from openpcrlib import OpenPCR

proghelp = '''\
How to write programs for OpenPCR:

Programs for OpenPCR should be written in YAML format.
This format specifies "key=value" pairs separated by
the ampersand ("&") symbol, as in:
"key1=value1&key2=value2"

All OpenPCR programs start with the pair "s=ACGTC".

If a new program is being uploaded, this is followed
by "c=start" to start the device, thus:
"s=ACGTC&c=start"

Additional keys specify global program parameters,
as well as the program itself. Global params are:

n: Program name. i.e. "n=OpenPyCR Test"
l: Lid temperature, i.e. "l=95"
d: A value used in verification, automatically added
    by OpenPyCR. Don't specify.
o: Contrast of the display on the device. In early
    models, this may instead be "t".

To format a program (keyed "p"), use this idiom:
p=(repetitions[s|t|label][s|t|label][s|t|label])

Where "s" is seconds and "t" is temperature. i.e.,
to program an archetypical PCR, use:
p=(35[20|95|Denature][10|55|Anneal][90|70|Extend])

Additional round-bracketed repeat statements may
be used to create more complex programs:
p=(35[20|95|Den][10|55|Ann][90|70|Ext])(1[999|4|Cool])

Programs cannot be longer than 252 characters.
Programs cannot have more than 16 'top level' steps.
Programs cannot have of more than 20 cycles.
Programs cannot have of more than 30 steps.
Lid temperature cannot be expressed as a decimal.
'''

class CursesDisplay():
    def __init__(self, screen, dev):
        self.scr = screen
        self.dev = dev

    def monitor(self):
        self.scr.nodelay(1) # Make self.scr.getch nonblocking.
        while True:
            self.printStatusMsg()
            time.sleep(1)
            char = self.scr.getch()
            if char != -1:
                break

    def writeln(self,string):
        self.scr.erase() # Clear window
        self.scr.addstr(0,0,string)
        self.scr.refresh()

    def printStatusMsg(self):
        S = self.dev.readstatus()
        try:
            PrettyStatus = 'Welcome to the OpenPyCR Real-time Monitor.\n'
            PrettyStatus += 'Current Program: {0}\n'.format(S['program'])
            PrettyStatus += ' Step "{0}" of cycle {1}\n'.format(S['currentstep'],str(S['cycle']))
            PrettyStatus += ' Currently: {0}\n'.format(S['job'])
            PrettyStatus += ' Block: {0}C, Lid: {1}C\n'.format(str(S['blocktemp']),str(S['lidtemp']))
            PrettyStatus += ' Remaining Time: {0}\n(Press any key to exit monitor mode)'.format(S['timeleft'])
        except KeyError:
            PrettyStatus = 'Run Finished.\n(Press any key to exit monitor mode)'
        self.writeln(PrettyStatus)

def CursesMonitor(dev):
    stdscr = curses.initscr()
    curses.cbreak()
    Console = CursesDisplay(stdscr, dev)
    Console.monitor()
    curses.nocbreak()
    curses.endwin()

#======= Functions for Terminal Use Follow ========
def status(device, args):
    device.printstatus()

def monitor(device, args):
    CursesMonitor(device)

def send(device, args):
    with args.program_file as InF:
        program = InF.read().strip()
    device.sendprogram(program)

def stop(device, args):
    device.stop()
    
def log(device, args):
    # args.interval and args.output_file
    with args.output_file as LogF:
        lastflush = time.time()
        try:
            while True:
                LogLine = device.csvstatus(args.columns)
                if device.active:
                    LogF.write(LogLine+"\n")
                else:
                    break
                if lastflush >= args.flush_interval:
                    lastflush = time.time()
                    LogF.flush()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass

P = argparse.ArgumentParser(
                description = "OpenPyCR: A pure-python controller and monitor for the OpenPCR Thermal Cycler.",
                epilog = "by Cathal Garvey, copyright 2013, released as Free Software under the GNU AGPL v3 or later.")
P.add_argument("-m","--device-mountpoint",default="/media/OPENPCR",type=str,
                    help="Path of the OpenPCR device. On Debian GNU/Linux (incl. Ubuntu) the default is usually correct.")
Subs = P.add_subparsers(help="Subcommands: Try calling '-h' or '--help' after these to get more specific help, if available.")

P_status = Subs.add_parser('status',help="Print a oen-time status message.")
P_status.set_defaults(function = status)

P_monitor = Subs.add_parser('monitor',help="Open a curses monitor for OpenPCR device.")
P_monitor.set_defaults(function = monitor)

P_send = Subs.add_parser('send',help="Send a string or file as a program to the OpenPCR device.")
P_send.add_argument("-p","--program_file",type=argparse.FileType("r"),default=sys.stdin,
                        help="Program to send. If not specified, reads from standard input.")
P_send.set_defaults(function = send)

P_stop = Subs.add_parser('stop',help='Send the stop signal to the OpenPCR to terminate current program.')
P_stop.set_defaults(function = stop)

P_log = Subs.add_parser('log',help='Print (or append to file) status information in csv format at set intervals.')
P_log.set_defaults(function = log)
P_log.add_argument("-i","--interval",type=int,default=5,help="Interval in seconds between log entries.")
P_log.add_argument("-o","--output-file",type=argparse.FileType("a"),default=sys.stdout,
                        help="File to append log output to. Default is stdout; print to terminal.")
P_log.add_argument("--columns",nargs="+",type=str,default=['currenttime','elapsedsecs','cycle','blocktemp'],
                        help="Columns to print to log. Options are: state job blocktemp lidtemp elapsedsecs secsleft currentstep cycle program nonce minsleft hoursleft timeleft currenttime")
P_log.add_argument("--flush-interval",type=int,default=30,
                        help="Interval by which to flush outut stream; may help prevent data loss on crash. If unsure, leave alone.")

P_proghelp = Subs.add_parser('proghelp',help='Print information on correct formatting for OpenPCR programs.')
P_proghelp.set_defaults(function = lambda x,y:print(proghelp))

# Parse arguments, and pass arguments into the associated function for handling
# according to appropriate subcommand.
A = P.parse_args()
Dev = OpenPCR(devicepath = A.device_mountpoint)
if not hasattr(A,"function"):
    P.print_usage()
else:
    A.function(Dev, A)
