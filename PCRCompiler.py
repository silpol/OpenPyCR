#!/usr/bin/env python3
'''PCRCompiler - Compiles from idiomatic higher-level instructions to OpenPCR programs.

OpenPCR accepts code in YAML format with the program compressed into a parenthesised
format, such as:
  s=ACGTC&l=95&c=start&n=CCR5(HIV Resistance)&p=(1[300|95|Initial Burn])(35[30|95|Denature][30|68|Annealing][30|72|Extension])        
This program would be better written in a MIME-style format, with headers first,
and programming instructions after a single blank line:

=======File Contents=======
Title: CCR5(HIV Resistance)
Lid: 95
Custom: Ignored

x1
    300s @ 95C Initial Burn
x35
    30s @ 95 Denature
    30s @ 68 Annealing
    30s @ 72 Extension
===========================

This format is pretty close to how one might normally denote a PCR program,
is highly readable and transmittable, and allows for optional custom headers
that are merely ignored.
'''

import re

_reps_re = re.compile("^x[0-9]+:?$")

class PCRStep:
    def __init__(self, seconds, temperature, title=''):
        self.seconds = seconds
        self.temperature = temperature
        self.title = title

    def __repr__(self):
        return "PCRStep({0}, {1}, '{2}')".format(self.seconds, self.temperature, self.title)

    def __str__(self):
        return '[{0}|{1}|{2}]'.format(self.seconds, self.temperature, self.title)

class PCRCycle:
    def __init__(self, reps, *steps):
        self.reps = reps
        self.steps = steps

    def __repr__(self):
        return "PCRCycle({0}, {1})".format(self.reps, ', '.join(repr(x) for x in self.steps))

    def __str__(self):
        return '({0}{1})'.format(self.reps, ''.join([str(x) for x in self.steps]))

class OpenPCRProgram:
    'Contains title, lid temperature, and a list of sub-steps. Can emit OpenPCR program strings.'
    def __init__(self, *cycles, title='', lid=95):
        self.cycles = cycles
        self.title = title
        self.lid = int(lid)

    def __repr__(self):
        return "OpenPCRProgram({0}, title='{1}', lid={2})".format(', '.join(repr(x) for x in self.cycles), self.title, self.lid)

    def __str__(self):
        return 's=ACGTC&l={0}&c=start&n={1}&p={2}'.format(self.lid, self.title, ''.join([str(x) for x in self.cycles]))

def count_indent(some_str):
    'Only applies to space characters; returns the number of indents. Not very performant.'
    return some_str.count(" ", 0, some_str.index(some_str.lstrip(" ")[0]) )

def parse_step_line(line):
    '''Steps of a PCR program are expected in this format: "XXs @ YYC Description",
    where XX is seconds (integer value), and YY is temperature in celsius. Description
    can be empty; this is the message that will be displayed on OpenPCR's screen, and
    should be sized to match. Descriptions add to program length, and as there is a
    maximum length, this should be considered when writing programs.'''
    line = line.strip()
    seconds, rest = [x.strip() for x in line.split("@")]
    if not rest:
        raise Exception("At least time and temperature must be specified in a step-defining line: '{0}'".format(line))
    seconds = seconds.lower().strip("s") # The s is really for clarity, can be omitted without bugs.. don't tell anyone!
    temperature, title = [x.strip() for x in rest.split(None,1)]
    temperature = temperature.lower().strip("c")
    try:
        seconds = int(seconds)
    except:
        raise Exception("Error: line contains non-permitted character where specifying time: '{0}'".format(line))
    try:
        temperature = float(temperature)
        if int(temperature) == temperature:
            temperature = int(temperature) # Save program space by omitting decimals.
        if temperature < 0 or temperature > 99:
            raise Exception("Error: OpenPCR should not be instructed to cool below freezing or heat above boiling.")
    except:
        raise Exception("Error: Line contains non-permitted character where specifying temperature: '{0}'".format(line))
    return PCRStep(seconds, temperature, title)

def parse_program(prog_string):
    '''Expects a multiline program of the type illustrated below. Compiles to an OpenPCRProgram object.
    Note: the whitespace separation between Title/Lid (and other meta?) is part
    of the format; if omitted it will create errors.
    
    Title: CCR5(HIV Resistance)
    Lid: 95

    x1
        300s @ 95C Initial Burn
    x35
        30s @ 95 Denature
        30s @ 68 Annealing
        30s @ 72 Extension
    '''
    # First, remove flanking whitespace, and end-of-line whitespace.
    prog_string = '\n'.join([x.rstrip() for x in prog_string.strip().splitlines()])

    # Split into headers and program lines.
    prog_headers, prog = prog_string.split("\n\n",1)
    headers = {}
    for line in prog_headers.splitlines():
        tag, value = [x.strip() for x in line.split(":",1)]
        headers[tag.lower()] = value.replace("&","+").replace("=",":") # Removing reserved YAML characters because shut up

    # Extract the two headers actually used; rest ignored.
    program_title = headers.get('title','')
    try:
        lid_temperature = abs(int(headers.get('lid','').lower().rstrip("c")))
        if not 0 <= lid_temperature <= 99:
            raise Exception("Program specifies a lid temperature not between 0C-99C; this is not recommended!")
    except:
        raise Exception("Lid temperature specified improperly. Must be of form 'Lid: 95C'.") # C is actually optional, ssh!

    # Now to parse the program instructions!
    cycles = []
    current_line = 0
    current_cycle_steps = []
    current_cycle_reps = 1
    current_indent = 0
    for line in prog.splitlines():
        current_line += 1
        indent = count_indent(line)
        if indent < current_indent:
            # Dedent means end of previous block, so use information to compile
            # a cycle and reset current_cycle_xxx bits.
            cycles.append(PCRCycle(current_cycle_reps, *current_cycle_steps))
            current_cycle_reps = 1
            current_cycle_steps = []
            current_indent = indent
        elif indent > current_indent > 0:
            raise Exception("Indentation must be consistent within program cycle blocks, and only one depth of indentation is currently supported.")
        elif indent > current_indent and current_indent == 0:
            # Indented block; must be a cycle.
            # If we already have steps accumulated, then this is erroneous further indentation!
            if current_cycle_steps:
                raise Exception("Additional steps indented above existing cycle depth on line {0}: '{1}'".format(current_line, line))
            current_cycle_steps.append(parse_step_line(line))
            current_indent = indent
        elif indent == current_indent and current_indent > 0:
            # Continued indented block of a cycle.
            current_cycle_steps.append(parse_step_line(line))
            current_indent = indent
        if indent == current_indent == 0:
            # Can only currently be either a number of repetitions for ensuing block,
            # or a single step, presumed non-repeated.
            if _reps_re.match(line):
                # Is a repetition-line, process to extract integer value
                # First check if repetition has previously been given; bug out
                if current_cycle_reps != 1:
                    raise Exception("Repetition value specified twice on line {0}: '{1}'".format(current_line, line))
                current_cycle_reps = int(line.strip("x:"))
            else:
                # Is a solitary line, process as a single-step cycle and proceed.
                # Check if a repetition value was given; syntax error.
                if current_cycle_reps != 1:
                    raise Exception("Repetition value given and not reset, but unindented (presumed solitary, non-repetitive) instruction found on line {0}: '{1}'".format(current_line, line))
                else:
                    # Parse line into time, temp and title, drop into PCRStep, then
                    # into PCRCycle, then into steps.
                    cycles.append(PCRCycle(parse_step_line(line)))
            current_indent = indent
    else:
        # Runs at end of For-loop to clean-up.
        if current_cycle_steps:
            cycles.append(PCRCycle(current_cycle_reps, *current_cycle_steps))
    return str(OpenPCRProgram(*cycles, title=program_title, lid=lid_temperature))

if __name__ == "__main__":
    import argparse
    P = argparse.ArgumentParser()
    P.add_argument("program",type=argparse.FileType("r"),help="Program to translate.")
    A = P.parse_args()
    with A.program as InF:
        print(parse_program(InF.read()))
