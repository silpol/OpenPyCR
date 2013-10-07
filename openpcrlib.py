import time
import sys
import os
import json
import subprocess

# Used by ncc:
import mmap
import ctypes
libc = ctypes.CDLL("libc.so.6")

def ncc(filen):
    '''Behaves like "no-cache-cat" (ncc) but in pure-python. Only works in GNU/Linux,
    as os.OS_DIRECT is a mirror of a GNU extension. The call to libc.posix_fadvise is
    essential and may not work correctly on all platforms.
    If this does not work correctly it is a silent failure; self-testing is essential
    to ensure that non-caching reads are executed successfully. If not, fallback to
    custom compiled C binaries would be necessary to get readouts.'''
    # Must be defined in case os.open call crashes and causes exception in finally block.
    f = 0
    os.sync()
    try:
        # os.O_DIRECT *should* mean "read directly from disc, bypassing cache",
        # but comes with a lot of bizzarre baggage regarding precise memory buffer
        # lengths and boundaries.
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
        #print("Exception attempting to open file with pyncc:",E,file=sys.stderr)
        raise IOError("Exception attempting to open file with pyncc: "+str(E))
    finally:
        # f is positive if successfully opened.
        if f > 0: os.close(f)
    # Return until first null character.
    return fc.split(b"\0",1)[0]


class PCRStep:
    def __init__(self, time_s, temp_c, title):
        self.time = time_s
        self.temp = temp_c
        self.title = title

    def __str__(self):
        return '[{0}|{1}|{2}]'.format(self.time, self.temp, self.title)
        
class PCRCycle:
    def __init__(self, repeats, *steps):
        selt.repeats = repeats
        self.steps = steps

    def __str__(self):
        return '({0}{1})'.format(self.repeats, ''.join([str(x) for x in self.steps]))

class OpenPCRProgram:
    def __init__(self, name, *cycles, lid_temp = 95):
        self.name = name
        self.lid_temp = lid_temp
        # Sample program:
        # s=ACGTC&l=95&c=start&
        # n=CCR5(HIV Resistance)&
        # p=(1[300|95|Initial Burn]) 
        #   (35[30|95|Denature][30|68|Annealing][30|72|Extension])        self.name = name
        # End sample
        # Pythonic representation:
        # PCRCycle(1, PCRStep(300, 95, "Initial Burn"), PCRCycle(35, PCRStep(30, 95, "Denature"), PCRStep(30, 68, "Annealing"), PCRStep(30, 72, Extension))
    def __str__(self):
        return 's=ACGTC&' + 'l={0}&c=start&n={1}&'.format(self.lid_temp, self.name) + ''.join([str(x) for x in self.cycles])

class OpenPCR:
    def __init__(self,devicepath=''):
        self.platform = sys.platform[:3]
        # Linux       'lin' (Also for POSIX generally?)
        # Cygwin      'cyg'
        # OS/2 (/EMX) 'os2'
        # Mac OS X    'dar'
        # Windows     'win'
        
        self.deviceath = devicepath or self.DefaultPlatformPath()

        if not os.path.exists(self.devicepath):
            print("Directory specified (default /media/OPENPCR) does not exist. Is OpenPCR turned on?")
            self.devicepath = ''
        assert(self.devicepath)

    def DefaultPlatformPath(self):
        'Checks "usual" mount locations on supported platforms and returns directory if successful.'
        # Use os.walk to seek out alternatives if not found?
        if self.platform == 'lin': return '/media/OPENPCR/' # Ubuntu mountpoint, at least.
        elif self.platform in ['win','dar','os2','cyg']:
            print({'win':"Windows",'dar':"Darwin/Mac",'cyg':"Cygwin/Windows",'os2':"OS/2"}[self.platform],
                    "is not yet supported, but *may* work if you manually invoke the OpenPCR object with",
                    "'devicepath' argument pointing to the OpenPCR device mountpoint.")
        else:
            print("Unknown platform; OpenPyCR is currently designed to work on Linux only.",
                  "You can try to manually invoke the OpenPCR object with 'devicepath' argument",
                  " pointing to the OpenPCR mountpoint, but don't get your hopes up.")

    def sendprogram(self, program):
        'Sends a program to the OpenPCR and prints a verification if successful.'
        assert(self.devicepath)
        Status = self.readstatus()
        CurrentNonce = Status['nonce']
        # Nonces should overflow, but no point going larger than 100; waste of transmitted chars!
        NewNonce = CurrentNonce + 1 if CurrentNonce < 100 else 1
        NonceCMD = 'd={}'.format(str(NewNonce))
        # Chop up program string, insert nonce, and reassemble for sending.
        dissectedprogram = program.split("&")
        for item in dissectedprogram:
            if item[0]=='d': # If there's already a nonce in this program for some reason..
                print("Found existing nonce value ('d=xxx') in program. Removing..")
                noncelistindex = dissectedprogram.index(item) # Find index to delete first..
                del(dissectedprogram[noncelistindex]) # Then kill it with fire.

        dissectedprogram.insert(1,NonceCMD) # Add new nonce to program.
        assembledprogram = "&".join(dissectedprogram) # Reassembles YAML-formatted program.
        self._sendprogram(assembledprogram)

        time.sleep(2) # If no waiting time is given, readstatus fails.
        started_waiting = time.time()
        Status = None
        while time.time() - started_waiting < 5:
            try:
                Status = self.readstatus()
                break
            except ValueError:
                print("Waiting for OpenPCR to respond..")
                time.sleep(0.5)
        if Status:
            if Status['nonce'] == NewNonce:
                print("Program sent successfully.")
            else:
                print("Nonce values unchanged; program may not have sent correctly.")
        else:
            print("OpenPCR not responding to checkstatus calls. Giving up.")

    def _sendprogram(self,program):
        # Removed encoding, unlikely it matters at all.
        with open(os.path.join(self.devicepath,'CONTROL.TXT'), mode='w') as Fout:
            Fout.write(program)

    def test(self):
        self.sendprogram('s=ACGTC&c=start&n=OpenPyCR Test Program&p=(20[10|45|TestStep1][20|25|TestStep2])')

    def stop(self):
        self.sendprogram('s=ACGTC&c=stop')

    def ncc(self):
        '''Low-level. Calls ncc binary for appropriate platform, returns raw output as string.
        Behaves like "no-cache-cat" (ncc) but in pure-python. Only works in GNU/Linux,
        as os.OS_DIRECT is a mirror of a GNU extension. The call to libc.posix_fadvise is
        essential and may not work correctly on all platforms.
        If this does not work correctly it is a silent failure; self-testing is essential
        to ensure that non-caching reads are executed successfully. If not, fallback to
        custom compiled C binaries would be necessary to get readouts.'''
        filen = os.path.join(self.devicepath,'STATUS.TXT')
        # Must be defined in case os.open call crashes and causes exception in finally block.
        f = 0
        os.sync()
        try:
            # os.O_DIRECT *should* mean "read directly from disc, bypassing cache",
            # but comes with a lot of bizzarre baggage regarding precise memory buffer
            # lengths and boundaries.
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
            #print("Exception attempting to open file with pyncc:",E,file=sys.stderr)
            raise IOError("Exception attempting to open file with pyncc: "+str(E))
        finally:
            # f is positive if successfully opened.
            if f > 0: os.close(f)
        # Return until first null character.
        return fc.split(b"\0",1)[0]

    def readstatus(self):
        'Calls ncc and translates output into a dictionary of values.'
        assert(self.devicepath)
        statustxt = self.ncc()
        status = dict([x.split("=") for x in statustxt.split("&")])
        statusd = {'state': status.get('s','Unknown'),
                   'job': status.get('t','Unknown'),
                   'blocktemp': float(status.get('b',0)),
                   'lidtemp': float(status.get('l',0)),
                   'elapsedsecs': int(status.get('e',0)),
                   'secsleft': int(status.get('r',0)),
                   'currentstep': status.get('p','Unknown'),
                   'cycle': int(status.get('c',0)),
                   'program': status.get('n','Unknown'),
                   'nonce': int(status.get('d',-1)),
                   }
        if statusd['nonce'] == -1:
            raise IOError("Received no program-identifier number from device - failure to communicate/reprogram?") 
        # Now to clean up TIME ITSELF
        statusd['minsleft'] = statusd['secsleft'] // 60
        statusd['hoursleft'] = statusd['minsleft'] // 60
        extramins = statusd['minsleft'] - (statusd['hoursleft'] * 60)
        extrasecs = statusd['secsleft'] - (statusd['minsleft'] * 60)
        statusd['timeleft'] = '{0}:{1}:{2}'.format(statusd['hoursleft'], extramins, extrasecs)
        statusd['currenttime'] = time.strftime("%H:%M:%S",time.localtime())
        return statusd

    def csvstatus(self,keyorder = ['currenttime','elapsedsecs','cycle','blocktemp']):
        '''Calls readstatus and formats output for logging to csv.

        keyorder is a list of dictionary keys to use, in desired order, when
        formatting output. The default provides the elapsed time in seconds,
        current cycle number, and temperature of the block.'''
        # Assemble keyworded formatting string from keyorder argument, then
        # unpack the dictionary result of self.readstatus into it to get return.
        return ', '.join(['{'+k+'}' for k in keyorder]).format(**self.readstatus())

    def printstatus(self):
        'Calls readstatus and prints useful information to stdout.'
        S = self.readstatus()
        if S['state'] == 'complete':  print("Program complete.")
        elif S['state'] == 'stopped': print("System idle. No program running.")
        elif S['state'] == "Unknown": print("System state unknown.")
        else:
            print(('Current Program: {program}\n'
                   "Step '{currentstep}' of cycle {cycle}\n"
                   "Currently: {job}\n"
                   "Block: {blocktemp}°C, Lid: {lidtemp}°C\n"
                   "Remaining Time: {timeleft}").format(**S))
   
