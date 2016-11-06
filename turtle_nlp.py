#!/usr/bin/env python3

import requests
import json
import sys
from collections import OrderedDict, defaultdict
import itertools

DEFAULT_BASE_URL = 'http://localhost:9000/'

def debugp(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class CompileError(Exception):

    def __init__(self, phrase, messages):
        self.phrase = phrase
        self.messages = messages
        self.message = 'Error in phrase: {}\n\t{}'.format(
            repr(self.phrase), '\n\t'.join([m for m in self.messages]))

    def __str__(self):
        return self.message

class Word:
    text = ''
    word_no = None  # Index of word in list of words in sentence
    pos = ''        # Part of speech
    phrase = ''     # Yield in dependency tree

    def __init__(self, text, word_no, pos):
        self.text = text
        self.word_no = word_no
        self.pos = pos
        self.edges = defaultdict(list) # keys are edge labels, values are words pointed by edges
        self.word_strs = set()  # type: Set[str] # set of words in phrase
        self.word_objs = [] # type: List[Word] # ordered list of words in phrase

    def __str__(self):
        return 'Word({}, word_no={}, pos={})'.format(self.text, self.word_no, self.pos)
    def __repr__(self):
        return str(self)

    def add_edge(self, edge_type, word):
        # type: (str, Word) -> None
            self.edges[edge_type].append(word)

    def get(self, edge_seq):
        # type: (Iterable[str]) -> List[Word]
        wordlist = [self]
        for edge in edge_seq:
            wordlist = list(itertools.chain.from_iterable((word.edges[edge] for word in wordlist)))
        return wordlist

    def edge_iter(self):
        for k, vlist in self.edges.items():
            for v in vlist:
                yield (k, v)
    def children_iter(self):
        for vlist in self.edges.values():
            for v in vlist:
                yield v

def print_preorder(word, edge_type='root', indent=0, file=sys.stdout):
    print('{}{}: {}, {}'.format('  '*indent, edge_type, repr(word.text), repr(word.phrase)), file=file)
    for edge_type2, word2 in sorted(word.edge_iter(), key=(lambda x: x[1].word_no)):
        print_preorder(word2, edge_type2, indent + 1)

def find_phrase(word):
    word.word_strs = {word.text}
    left_word_objs = []
    right_word_objs = []
    sorted_words = sorted(word.children_iter(), key=(lambda x: x.word_no))
    for word2 in sorted_words:
        find_phrase(word2)
        if word2.word_no < word.word_no:
            left_word_objs += word2.word_objs
        else:
            right_word_objs += word2.word_objs
        word.word_strs |= word2.word_strs
    word.word_objs = left_word_objs + [word] + right_word_objs
    word.phrase = ' '.join([w.text for w in word.word_objs])

def parse_text(text, server_url):

    params = {'properties': "{'annotators': 'pos,depparse', 'outputFormat': 'json'}"}

    r = requests.post(server_url, params=params, data=text)
    r.raise_for_status()

#   debugp(json.dumps(r.json(), indent=2))

    return [parse_sentence(sentence, text) for sentence in r.json()['sentences']]

def parse_sentence(sentence, text):
    """Analyzes a JSON sentence and returns the root word object"""
    words_list = []
    words_dict = OrderedDict()
    least_index = 1<<30
    highest_index = 0
    for token in sentence['tokens']:
        word = Word(token['word'], token['index'], token['pos'])
        words_list.append(word)
        words_dict[token['word']] = word
        least_index = min(least_index, token['characterOffsetBegin'])
        highest_index = max(highest_index, token['characterOffsetEnd'])

    root = None
    for edge in sentence['basic-dependencies']:
        governor_index = edge['governor']
        dependent = words_list[edge['dependent'] - 1]
        edge_type = edge['dep']
        if governor_index == 0:
            root = dependent
        else:
            governor = words_list[governor_index - 1]
            governor.add_edge(edge_type, dependent)

    find_phrase(root)
    return root

class CSR:
    """Control Structure Recognizer
    There are 2 types of CSR, terminal CSRs and non-terminal CSRs.
    Terminal CSRs will directly produce target code
    Non-terminal CSRs will split phrases into parts to be handled by other CSRs.
    """

    def detect(self, word, env=None):
        """
        Detect whether this control structure exists in a particular text.
        Output parameters of this control structure if it exists, otherwise output None.
        If it is found that the control structure is correct but has been used wrongly, raise a
        """
        pass

    def apply(self, word, params, env=None):
        """
        Output turtle code for this CSR for the phrase represented by word.
        Raise a CompilerError exception with error messages for the user if needed.
        """
        pass

def get_names(dobj_word, errmsgs):

    def is_name_word(x):
        return x.pos == 'NNP' or x.text in ('turtle', 'everyone')

    name_words = []
    if 'cc' in dobj_word.edges and 'conj' in dobj_word.edges:
        if [w.text for w in dobj_word.edges['cc']] != ['and']:
            errmsgs.append("Turtle names must be connected by 'and'.")
    and_names = dobj_word.edges['conj'] + [dobj_word]
    final_names = []
    for name in and_names:
        if is_name_word(name):
            final_names.append(name)
        elif 'compound' in name.edges:
            compound_edges = name.edges['compound']
            if len(compound_edges) == 1 and is_name_word(compound_edges[0]):
                final_names.append(compound_edges[0])
                # This is a workaround for a bug where CoreNLP makes measurement unit
                # a direct object and the actual direct object is connected to the
                # measurement unit by a 'compound' edge.
        else:
            errmsgs.append('{} is not a valid name'.format(name.text))
    return final_names

class MoveCSR(CSR):

    def __str__(self):
        return 'MoveCSR()'
    def __repr__(self):
        return str(self)

    directions = {'ahead': 'fd',
        'forward': 'fd',
        'forwards': 'fd',
        'backward': 'bk',
        'backwards': 'bk',
        'up': 'up',
        'upward': 'up',
        'upwards': 'up',
        'down': 'down',
        'downward': 'down',
        'downwards': 'down',
        'left': 'left',
        'leftward': 'left',
        'leftwards': 'left',
        'anticlockwise': 'left',
        'counterclockwise': 'left',
        'right': 'right',
        'rightward': 'right',
        'rightwards': 'right',
        'clockwise': 'right',
    }
    units = {
        'unit': 'pixel',
        'units': 'pixel',
        'step': 'pixel',
        'steps': 'pixel',
        'pixel': 'pixel',
        'pixels': 'pixel',
        'degree': 'deg',
        'degrees': 'deg',
        'radian': 'rad',
        'radians': 'rad',
    }
    actions = {
        'move': 'move',
        'shift': 'move',
        'turn': 'turn',
        'rotate': 'turn',
    }

    def detect(self, word, env=None):
        """
        A phrase is roughly a movement command if:
        1. It has the word 'move', 'turn', etc and that is a verb.
        2. There is a proper noun in the phrase (which is the name of the turtle).
        4. It has the word 'forward' or 'backward' or 'upward' etc.
        3. It has the word 'units' or 'pixels' with a number adjoining it.
        """
        action_words = [word for word in word.word_objs
            if word.text.lower() in self.actions and word.pos == 'VB']
        proper_nouns = [word for word in word.word_objs if word.pos == 'NNP']
        direction_words = [word for word in word.word_objs if word.text in self.directions]
        unit_words = [word for word in word.word_objs if word.text in self.units]

        """
        debugp('MoveCSR: {}:'.format(repr(word.phrase)))
        debugp('\taction_words={}'.format(action_words))
        debugp('\tname_words={}'.format(name_words))
        debugp('\tdirection_words={}'.format(direction_words))
        debugp('\tunit_words={}'.format(unit_words))
        """

        if len(action_words) > 1:
            debugp('warning: MoveCSR: Multiple action words detected in phrase:\n{}'.format(word.phrase))

        if not (len(action_words) == 1 and len(unit_words) == 1):
            return None

        action_word = action_words[0]
        unit_word = unit_words[0]

        params = {}
        errmsgs = []
        params["action"] = self.actions[action_word.text.lower()]
        params["unit"] = self.units[unit_word.text]

        try:
            params["amount"] = unit_word.get(['nummod'])[0].text
        except IndexError:
            return None

        if len(direction_words) == 0:
            errmsgs.append("Movement direction not specified.")
        elif len(direction_words) > 1:
            errmsgs.append("Too many directions have been specified.")
        else:
            params["direction"] = self.directions[direction_words[0].text]

        dobj_words = action_word.get(['dobj'])
        if len(dobj_words) == 0:
            raise CompileError(word.phrase, ["No direct object found"])
        elif len(dobj_words) > 1:
            errmsgs.append("Multiple direct objects not expected.")
        name_words = get_names(dobj_words[0], errmsgs)
        params["names"] = [name_word.text.lower() for name_word in name_words]

        if errmsgs:
            raise CompileError(word.phrase, errmsgs)
        return params

    def apply(self, word, params, env=None):
        raw_amount = params["amount"]
        try:
            amount = float(raw_amount)
        except ValueError:
            raise CompilerError(word.phrase, ['{} is not a valid number.'.format(repr(raw_amount))])

        action = params["action"]
        unit = params["unit"]
        direction = params["direction"]
        names = params["names"]

        errmsgs = []
        if action == 'move':
            if unit != 'pixel':
                unit_errmsg = 'Incorrect unit {} for action {}.'.format(
                    repr(unit), repr(action))
                errmsgs.append(unit_errmsg)
            if direction in ['fd', 'bk', 'up', 'down']:
                output = [' '.join([direction, name, str(amount)]) for name in names]
            elif direction == 'left':
                output = [' '.join(['shl', name, str(amount)]) for name in names]
            elif direction == 'right':
                output = [' '.join(['shr', name, str(amount)]) for name in names]
            else:
                dir_errmsg = 'Incorrect direction {} for action {}.'.format(
                    repr(direction), repr(action))
                errmsgs.append(direrrmsg)
        elif action == 'turn':
            if unit in ['deg', 'rad']:
                output = [' '.join([unit, name]) for name in names]
                if direction == 'left':
                    output += [' '.join(['rol', name, str(amount)]) for name in names]
                elif direction == 'right':
                    output += [' '.join(['ror', name, str(amount)]) for name in names]
                else:
                    dir_errmsg = 'Incorrect direction {} for action {}.'.format(
                        repr(direction), repr(action))
                    errmsgs.append(direrrmsg)
            else:
                unit_errmsg = 'Incorrect unit {} for action {}.'.format(
                    repr(unit), repr(action))
                errmsgs.append(unit_errmsg)

        if errmsgs:
            raise CompileError(word.phrase, errmsgs)
        else:
            return output

terminal_CSRs = [MoveCSR()]
nonterminal_CSRs = []

def get_csrs(word, csr_list):
    csr_params = {}
    for csr in csr_list:
        params = csr.detect(word)
        if params is not None:
            csr_params[csr] = params
    return csr_params

def apply_csrs(word, csr_list):
    csr_params = get_csrs(word, csr_list)
    if len(csr_params) > 1:
        raise CompileError(word.phrase, ["Multiple CSRs detected: " + ', '.join([str(csr) for csr in csr_params])])
    elif len(csr_params) == 1:
        csr, params = list(csr_params.items())[0]
        output = csr.apply(word, params)
        return output
    else:
        return None

from pprint import pprint

def debug_csrs(text, server_url):
    sentences = parse_text(text, server_url)
    for s in sentences:
        print_preorder(s)
        csr_params = get_csrs(s, nonterminal_CSRs + terminal_CSRs)
        pprint(csr_params)

def convert(word):
    output = apply_csrs(word, nonterminal_CSRs) or apply_csrs(word, terminal_CSRs)
    if output is None:
        raise CompileError(word.phrase, ["Couldn't recognize sentence structure."])
    else:
        return output

def text_to_turtle(gen, server_url, prompt='', promptfile=None):
    gen = iter(gen)
    while True:
        if promptfile is not None and prompt:
            promptfile.write(prompt)
            promptfile.flush()
        text = next(gen).strip()
        if text:
            sentences = parse_text(text, server_url)
            for s in sentences:
                try:
                    output = convert(s)
                    for line in output:
                        yield line
                except CompileError as e:
                    print(e, file=sys.stderr)

from inpr import Interpreter
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', nargs='?',
        help='Natural language source to interpret. Open interactive shell if not specified.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', metavar='object_file', dest='object_file',
        help='Compile source to object code and store in this file.')
    group.add_argument('-d', '--debug', action='store_true', default=False,
        help='Debugging: Detect CSRs and report params.')
    parser.add_argument('--server', default=DEFAULT_BASE_URL,
        help='URL of CoreNLP server to connect to.')
    args = parser.parse_args()

    if args.debug:
        if args.source is not None:
            print("Error: Source file should not be specified while debugging", file=sys.stderr)
        else:
            try:
                while True:
                    text = input('debug> ').strip()
                    if text:
                        debug_csrs(text, args.server)
            except EOFError:
                pass
            print()
    elif args.object_file is not None:
        if args.source is None:
            print("Error: Source file not specified.", file=sys.stderr)
        else:
            with open(args.source) as sobj:
                with open(args.object_file, 'w') as oobj:
                    for line in text_to_turtle(sobj, args.server):
                        print(line, file=oobj)
    else:
        if args.source is None:
            tt = text_to_turtle(sys.stdin, args.server, '>>> ', sys.stdout)
            inpr = Interpreter(tt, sys.stdout)
            inpr.run()
            print()
        else:
            with open(args.source) as sobj:
                tt = text_to_turtle(sobj, args.server)
                inpr = Interpreter(tt, sys.stdout)
                inpr.run()

if __name__ == '__main__':
    main()
