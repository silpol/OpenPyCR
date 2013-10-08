import time
import sys
import os
import json
import subprocess
import mmap

if "linux" not in sys.platform:
    print("OpenPyCR uses system calls that are only available on Linux platforms. Your platform -",
            sys.platform,"- is probably incompatible, so reading OpenPCR status is probably impossible and this",
            "program will probably crash. This is *not a bug* if you are using a platform other",
            "than linux, and there is no plan to support non-free/libre platforms.", file=sys.stderr)
if sys.version_info[:2] < (3,3):
    # native posix_fadvise introduced in 3.3, can shim in with ctypes:
    print("Your Python version is outdated and lacks the posix_fadvise system call in os.",
          "Attempting to shim this in using ctypes..", file=sys.stderr)
    import ctypes
    try:
        os.POSIX_FADV_NORMAL     = 0
        os.POSIX_FADV_RANDOM     = 1
        os.POSIX_FADV_SEQUENTIAL = 2
        os.POSIX_FADV_WILLNEED   = 3
        os.POSIX_FADV_DONTNEED   = 4
        os.POSIX_FADV_NOREUSE    = 5
        # The above will (or should?) always work, so do that first.
        libc = ctypes.CDLL("libc.so.6")
        os.posix_fadvise = libc.posix_fadvise
        print("posix_fadvise shim successful, nothing to see here. Consider updating Python anyway.", file=sys.stderr)
    except OSError:
        print("Attempted to open libc.so.6 to import the posix_fadvise system call failed.",
              "Reading from OpenPCR will not function correctly as disk/os level caching will interfere.",file=sys.stderr)
        # Add an empty shim so it doesn't crash later.
        if not hasattr(os, "posix_fadvise"): os.posix_fadvise = lambda w,x,y,a:None

# === Not yet used ===
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
# ====================

class OpenPCRError(Exception):
    pass

class OpenPCR:
    def __init__(self,devicepath=''):
        self.devicepath = devicepath or '/media/OPENPCR/'
        self.active = False

    @property
    def ready(self):
        if os.path.exists(self.devicepath) and os.path.exists(os.path.join(self.devicepath,"STATUS.TXT")):
            return True
        else:
            return False

    def sendprogram(self, program):
        'Sends a program to the OpenPCR and prints a verification if successful.'
        if not self.ready:
            raise OpenPCRError("Cannot send program as device is not ready.")
        # TODO: Clean this mess up.
        CurrentNonce = self.readstatus()['nonce']
        # Nonces should overflow, but no point going larger than 99, maybe even 9.
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
        with open(os.path.join(self.devicepath,'CONTROL.TXT'), mode='w') as Fout:
            Fout.write(program)

    def test(self):
        self.sendprogram('s=ACGTC&c=start&n=OpenPyCR Test Program&p=(20[10|45|TestStep1][20|25|TestStep2])')

    def stop(self):
        self.sendprogram('s=ACGTC&c=stop')

    def ncc(self):
        '''Low-level. Calls ncc binary for appropriate platform, returns raw output as string.
        Behaves like "no-cache-cat" (ncc) but in pure-python. Only works on Unix, possibly Linux.
        If this does not work correctly it is a silent failure; self-testing is essential
        to ensure that non-caching reads are executed successfully. If not, fallback to
        custom compiled C binaries would be necessary to get readouts.'''
        if not self.ready:
            raise OpenPCRError("Device not ready, cannot read status.")
        filen = os.path.join(self.devicepath,'STATUS.TXT')
        with open(filen,"rb") as InF:
            os.posix_fadvise(InF.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
            fc = InF.read()
        # Return until first null character.
        # Reading in non-binary mode leads to odd extra whitespace due to nulls
        # followed by whitespace; trimming nulls from a string seems silly, so
        # stick to binary, strip and decode; let Python re-null strings as desired.
        return fc.split(b"\0",1)[0].decode()

    def readstatus(self):
        'Calls ncc and translates output into a dictionary of values.'
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
        self.active = False if statusd['state'] in ['Complete','Inactive'] else True
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
   
