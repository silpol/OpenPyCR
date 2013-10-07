#!/usr/bin/env python3
import curses
import time
import sys
from openpcrlib import OpenPCR

class CursesDisplay():
    def __init__(self,scr):
        self.scr = scr

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
        S = Dev.readstatus()
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

def CursesMonitor():
    stdscr = curses.initscr()
    curses.cbreak()
    Console = CursesDisplay(stdscr)
    Console.monitor()
    curses.nocbreak()
    curses.endwin()

def usage():
    print("Usage: openpycr [option] <args..>\nOptions:")
    print(" status - Print a one-time status message.")
    print(" monitor - Open a curses monitor for OpenPCR device")
    print(" sendstring <string> - Send a program string to the device")
    print(" sendprogram <file> - Upload a program from flat text file or\n       stdin (use '-') to the device")
    print(" stop - Send a stop signal to the device")
    print(" log <interval> <file> - Append csv-formatted log data every\n       <interval> seconds to a file or stdout (use '-')")
    print(" proghelp - Print information on how to format programs.")
    print(" about - Print an informative message about OpenPyCR.")

Dev = None
def initOpenPCR():
    try:
        Dev = OpenPCR()
        return Dev
    except AssertionError:
        print("OpenPCR not available at specified mountpoint.",file=sys.stderr)
        exit(1)

if len(argv) < 2:
    usage()
elif sys.argv[1] == 'status':
    Dev = initOpenPCR()
    Dev.printstatus()
elif sys.argv[1] == 'monitor':
    Dev = initOpenPCR()
    CursesMonitor()
elif sys.argv[1] == 'stop':
    Dev = initOpenPCR()
    Dev.stop()
elif sys.argv[1] == 'sendstring':
    Dev = initOpenPCR()
    if len(argv) != 3:
        print("You must provide a program string.")
        usage()
    else:
        print("Sending: "+argv[2])
        Dev.sendprogram(argv[2])
elif sys.argv[1] == 'sendprogram':
    Dev = initOpenPCR()
    if len(argv) != 3:
        print("You must provide a file to upload. Use '-' for stdin.\n Programs must be in YAML format.")
        usage()
    else:
        if sys.argv[2] == '-':
            Program = sys.stdin.read().strip()
            print(Program)
            Dev.sendprogram(Program)
        else:
            with open(argv[2], encoding='utf-8', mode='r') as ReadIn:
                Program = ReadIn.read().strip()
            Dev.sendprogram(Program)
elif sys.argv[1] == 'log':
    Dev = initOpenPCR()
    if len(argv) != 4:
        print("You must provide a logging interval and an output.\n Use '-' to specify stdout.")
        usage()
    else:
        interval = int(argv[2])
        if sys.argv[3] == '-':
            while True:
                LogLine = Dev.csvstatus()
                if LogLine == 'Complete':
                    break # Don't provide feedback, might break piping.
                if LogLine == 'Inactive':
                    print("Program not running; OpenPCR Inactive.")
                    break
                print(LogLine)
        else:
            logfile = sys.argv[3]
            with open(logfile, encoding='utf-8', mode='a') as LogFile:
                while True:
                    LogLine = Dev.csvstatus()
                    if LogLine == 'Complete':
                        print("Program complete, no more logs to give.")
                        break
                    elif LogLine == 'Inactive':
                        print("Program not running; OpenPCR Inactive.")
                        break
                    else:
                        LogFile.write(LogLine+'\n')
                    time.sleep(interval)
elif sys.argv[1] == 'about':
    print("Foo")
    with open("README.md", encoding='utf-8', mode='r') as ReadIn:
        AboutMsg = ReadIn.read()
    print(AboutMsg)
        
elif sys.argv[1] == 'proghelp':
    print('''How to write programs for OpenPCR:

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
''')
