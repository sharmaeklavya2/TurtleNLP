#!/usr/bin/env python3
"""
An interpreter for a custom turtle programming language called tortuga.
All instructions have an opcode followed by one or more operands.
Number of arguments for each opcode is fixed.
"""

import turtle
import sys

opcodes = {
    # Here x is the first arg and y is the second arg
    # basic commands
    'fd': [str, float],    # forward
    'bk': [str, float],    # backward
    'rol': [str, float],   # rotate left
    'ror': [str, float],   # rotate right
    'shl': [str, float],   # shift left (anti-clockwise)
    'shr': [str, float],   # shift right (clockwise)
    'up': [str, float],
    'down': [str, float],
    'deg': [str],   # set angle measure to degrees for turtle x
    'rad': [str],   # set angle measure to radians for turtle x
    'create': [str],    # create a new turtle
    'destroy': [str],   # destroy a turtle
    # control commands
    'repeat': [int],    # repeat a code block x times
    'end': [],   # end of code block
}

def check_types(values, types):
    n = len(values)
    if n != len(types):
        return False
    for i in range(n):
        value = values[i]
        typ = types[i]
        try:
            typ(value)
        except ValueError:
            return False
    return True

class InterpreterError(Exception): pass

class Interpreter:

    def __init__(self, gen, outfile=None, prompt='', promptfile=None):
        # gen should be generator of strings (including file-like objects).
        self.turtles = []
        self.history = []
        self.line_no = 0
        self.num_stack = []
        self.line_stack = []
        self.depth = 0

        self.gen = gen
        self.outfile = outfile
        self.prompt = prompt
        self.promptfile = promptfile

    def basic_interpret(self, op, args):
        if self.outfile is not None:
            print(op + " " + " ".join(args), file=self.outfile)

    def run(self):
        while True:
            if self.line_no == len(self.history):
                """
                if self.mode == 0:
                    self.history.clear()
                    self.line_no = 0
                """
                try:
                    if self.promptfile is not None and self.prompt:
                        self.promptfile.write(self.prompt)
                        self.promptfile.flush()
                    instr = next(self.gen).strip()
                except StopIteration:
                    return
                if instr:
                    self.history.append(instr)
                else:
                    continue

            instr = self.history[self.line_no]
            op, *args = instr.split()
            if op not in opcodes:
                raise InterpreterError("Invalid opcode {}".format(repr(op)))
            elif len(args) != len(opcodes[op]):
                raise InterpreterError("Invalid number of arguments for {}".format(repr(op)))
            elif check_types(args, opcodes):
                raise InterpreterError("Invalid types")

            if self.depth > 0:
                if op == 'repeat':
                    self.depth += 1
                elif op == 'end':
                    self.depth -= 1
                self.line_no += 1
            elif op == 'repeat':
                times = int(args[0])
                if times == 0:
                    self.depth += 1
                else:
                    self.num_stack.append(times - 1)
                    self.line_stack.append(self.line_no + 1)
                self.line_no += 1
            elif op == 'end':
                if len(self.num_stack) == 0:
                    raise InterpreterError("unmatched end")
                if self.num_stack[-1] == 0:
                    self.num_stack.pop()
                    self.line_stack.pop()
                    self.line_no += 1
                else:
                    self.num_stack[-1] -= 1
                    self.line_no = self.line_stack[-1]
            else:
                self.basic_interpret(op, args)
                self.line_no += 1

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', nargs='?',
        help='Turtle source code to intrepret. Open interactive shell if not specified.')
    args = parser.parse_args()

    if args.file is None:
        print("Turtle interpreter")
        inpr = Interpreter(sys.stdin, sys.stdout, '>>> ', sys.stderr)
        inpr.run()
        print()
    else:
        with open(args.file) as fobj:
            inpr = Interpreter(fobj, sys.stdout)
            inpr.run()

if __name__ == '__main__':
    main()
