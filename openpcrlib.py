import time, sys, os.path, json
from subprocess import check_output

class OpenPCR:
    def __init__(self,devicepath=''):
        self.platform = sys.platform[:3]
        # Linux 	'lin'
        # Windows	'win'
        # Cygwin 	'cyg'
        # Mac OS X	'dar'
        # OS/2 (/EMX)	'os2'
        
        if not devicepath: #i.e. if none was passed at object initiation..
            self.devicepath = self.DefaultPlatformPath()
        else:
            self.devicepath = devicepath # Just assume user knows what s/he is doing..

        if not os.path.exists(self.devicepath):
            print("Directory specified (default /media/OPENPCR) does not exist. Is OpenPCR turned on?")
            self.devicepath = ''
        assert(self.devicepath)

    def DefaultPlatformPath(self):
        'Checks "usual" mount locations on supported platforms and returns directory if successful.'
        if self.platform == 'lin':
            return '/media/OPENPCR/' # Ubuntu mountpoint, at least.
            # TODO: Cascade through potential mountpoints on other linuxes, using os.path.exists()?
        elif self.platform == 'win':
            print("Windows not yet supported. You can try manually invoking the OpenPCR() object with a "+\
                  "'devicepath' argument consisting of the openpcr mountpoint, if you like; be sure to "+\
                  "share your results if it works!")
            return ''
        elif self.platform == 'dar':
            print("Mac/Darwin not yet supported. You can try manually invoking the OpenPCR() object with a "+\
                  "'devicepath' argument consisting of the openpcr mountpoint, if you like; be sure to "+\
                  "share your results if it works!")
            return ''
        elif self.platform == 'os2':
            print("OS/2 not yet supported. You can try manually invoking the OpenPCR() object with a "+\
                  "'devicepath' argument consisting of the openpcr mountpoint, if you like; be sure to "+\
                  "share your results if it works!\n"+\
                  "Please note, there is no 'ncc' binary for OS2, so reading OpenPCR status is not possible.")
            return ''
        elif self.platform == 'cyg':
            print("Cygwin not yet supported. You can try manually invoking the OpenPCR() object with a "+\
                  "'devicepath' argument consisting of the openpcr mountpoint, if you like; be sure to "+\
                  "share your results if it works!")
            return ''

    def sendprogram(self,program):
        'Sends a program to the OpenPCR and prints a verification if successful.'
        assert(self.devicepath)
        Status = self.readstatus()
        CurrentNonce = Status['nonce']
#        CurrentNonce = 65534 # For debugging purposes only, replace with the above..
        if CurrentNonce < 65535: # Max int size on arduino; wrap around to avoid bugs.
            NewNonce = CurrentNonce + 1
        else:
            NewNonce = 1
        NonceCMD = 'd=' + str(NewNonce)
        
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
        recurse = 0
        def checkNonce():
            try:
                Status = self.readstatus()
                if Status['nonce'] == NewNonce:
                    print("Program sent successfully!")
                else:
                    print("Nonce values unchanged; program may not have sent correctly.")
            except ValueError:
                if recurse < 6: # Max 5 seconds wait after initial second.
                    print("Waiting for OpenPCR to respond..")
                    time.sleep(1)
                    recurse += 1
                    checkNonce() # Recursive function calls, yay! (Puppies may die.)
                else:
                    print("OpenPCR not responding to checkstatus calls. Giving up.")
        checkNonce() # Start checking.

    def _sendprogram(self,program):
        assert(self.devicepath)
        with open(self.devicepath+'CONTROL.TXT', encoding='utf-8', mode='w') as ProgramPipe:
            ProgramPipe.write(program)

    def test(self):
        assert(self.devicepath)
        self.sendprogram('s=ACGTC&c=start&n=OpenPyCR Test Program&p=(20[10|45|TestStep1][20|25|TestStep2])')

    def stop(self):
        assert(self.devicepath)
        self.sendprogram('s=ACGTC&c=stop')

    def ncc(self):
        'Low-level. Calls ncc binary for appropriate platform, returns raw output as string.'
        if (self.platform == 'lin') or (self.platform == 'dar'): # Assuming that mac uses same binary here..
            try:
                ByteStatus = check_output(["./ncc", self.devicepath+"STATUS.TXT"])
            except:
                print("'ncc' binary exited with an error. Platform may be incompatible.")
        elif (self.platform == 'win') or (self.platform == 'cyg'): # Assuming cygwin calls windows binary.
            try:
                ByteStatus = check_output(["./ncc.exe", self.devicepath+"STATUS.TXT"]) # Totally untested.
            except:
                print("'ncc.exe' binary exited with an error. Platform may be incompatible.")
        else:
            print("System not supported.")
            return None
        StrStatus = str(ByteStatus, encoding='utf-8')
        return StrStatus

    def readstatus(self):
        'Calls ncc and translates output into a dictionary of values.'
        assert(self.devicepath)
        statustxt = self.ncc()
        statusdict = {}
        for entry in statustxt.split("&"):
            key, val = entry.split("=")
            if key == 's': # State: running, idle, etc.
                statusdict['state'] = val
            elif key == 't': # Job: Heating/Cooling/Holding
                statusdict['job'] = val
            elif key == 'b': # Temperature of the block; Celsius.
                statusdict['blocktemp'] = float(val)
            elif key == 'l': # Temperature of the lid; Celsius.
                statusdict['lidtemp'] = float(val)
            elif key == 'e': # Elapsed seconds.
                statusdict['elapsedsecs'] = int(val)
            elif key == 'r': # Remaining seconds (accuracy?).
                secs = int(val) # Converts from string to int.
                mins = int(secs/60) # int() omits decimals.
                hours = int(mins/60)
                statusdict['secsleft'] = secs
                statusdict['minsleft'] = mins
                statusdict['hoursleft']= hours
                 # Remainders, for hours:mins:seconds
                extramins = mins - (hours*60)
                extrasecs = secs - (mins*60)
                formattedtime = '{0}:{1}:{2}'.format(hours,extramins,extrasecs)
                statusdict['timeleft'] = formattedtime
            elif key == 'p': # Name of current step, if given.
                statusdict['currentstep'] = val
            elif key == 'c': # Cycle number.
                statusdict['cycle'] = int(val)
            elif key == 'n': # Program name, if given.
                statusdict['program'] = val
            elif key == 'd':
                # The "number-used-once" that helps verify program sending.
                # No other function, generally safe to ignore except when
                # testing program delivery.
                statusdict['nonce'] = int(val)
        return statusdict

    def csvstatus(self,keyorder = ['elapsedsecs','cycle','blocktemp']):
        '''Calls readstatus and formats output for logging to csv.

        keyorder is a list of dictionary keys to use, in desired order, when
        formatting output. The default provides the elapsed time in seconds,
        current cycle number, and temperature of the block.'''
        assert(self.devicepath)
        S = self.readstatus()
        if (S['state'] == 'stopped') or (S['job'] == 'idle'):
            return 'Inactive' # OpenPCR not running, will probably raise keyerrors below if we proceed.
        if (S['state'] == 'complete'):
            return 'Complete'
        thisline = []
        try:
            for key in keyorder:
                thisline.append(str(S[key]))
            return ','.join(thisline)
        except KeyError:
            print("Provided keys invalid. Available keys are: state, job, blocktemp, lidtemp, elapsedsecs, secsleft, minsleft, hoursleft, timeleft, currentstep, cycle, program, nonce.")

    def printstatus(self):
        'Calls readstatus and prints useful information to stdout.'
        assert(self.devicepath)
        S = self.readstatus()
        if S['state'] == 'complete':
            print("Program complete.")
            return None
        if S['state'] == 'stopped':
            print("System idle. No program running.")
            return None
        PrettyStatus = '''Current Program: {0}
 Step '{1}' of cycle {2}
 Currently: {3}
 Block: {4}°C, Lid: {5}°C
 Remaining Time: {6}'''.format(S['program'],S['currentstep'],str(S['cycle']),S['job'],str(S['blocktemp']),str(S['lidtemp']),S['timeleft'])
        print(PrettyStatus)

