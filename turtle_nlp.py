#!/usr/bin/env python3

import requests
import json
import sys
from collections import OrderedDict, defaultdict
import itertools

DEFAULT_BASE_URL = 'http://localhost:9000/'

def debugp(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class CompileError:

    def __init__(self, word, errcode=''):
        self.errcode = errcode or 'ERR'
        self.word = word
        self.message = 'An error occured.'

    def __repr__(self):
        return 'CompileError({}, {}, {})'.format(repr(self.errcode), repr(self.phrase), repr(self.message))

    def __str__(self):
        return self.message

class CEList(Exception):
    errors = ()

    def __init__(self, errors):
        self.errors = errors
        self.errcodes = [error.errcode for error in errors]
        errors_by_word_no = defaultdict(list)
        for error in errors:
            errors_by_word_no[error.word.word_no].append(error)
        lines = []
        for word_no, error_list in sorted(errors_by_word_no.items(), key=(lambda x: x[0])):
            lines.append('Error in phrase: ' + error_list[0].word.phrase)
            for error in error_list:
                lines.append('\t{}: {}'.format(error.errcode, error.message))
        self.message = '\n'.join(lines)

    def __str__(self):
        return self.message

class NoCSRCE(CompileError):
    def __init__(self, word, errcode=''):
        CompileError.__init__(self, word, errcode or 'NOCSR')
        self.message = 'No CSR was detected.'

class ManyCSRCE(CompileError):
    def __init__(self, word, errcode='', csr_list=()):
        CompileError.__init__(self, word, errcode or 'MANYCSR')
        self.message = 'Multiple CSRs detected: {}.'.format(csr_list)
        self.csr_list = csr_list

class MissingDataCE(CompileError):
    def __init__(self, word, errcode='', param=''):
        CompileError.__init__(self, word, errcode or 'NODATA')
        self.message = 'No value specified for {}.'.format(repr(param))
        self.param = param

class BadDataCE(CompileError):
    def __init__(self, word, errcode='', param='', value=''):
        CompileError.__init__(self, word, errcode or 'BADDATA')
        self.message = '{} is an invalid value for {}.'.format(repr(value), repr(param))
        self.param = param
        self.value = value

class BadCCCE(CompileError):
    def __init__(self, word, errcode='', objtype='', cc=''):
        CompileError.__init__(self, word, errcode or 'BADCC')
        self.message = '{} should be connected by {}.'.format(objtype, repr(cc))
        self.objtype = objtype
        self.cc = cc

class TooManyValuesCE(CompileError):
    def __init__(self, word, errcode='', param=''):
        CompileError.__init__(self, word, errcode or 'MANYVAL')
        self.message = 'Too many values specified for {}.'.format(repr(param))
        self.param = param

class TooManyOccsCE(CompileError):
    def __init__(self, word, text=''):
        CompileError.__init__(self, word, errcode or 'MANYOCCS')
        self.message = 'Too many occurences of {}.'.format(repr(text))
        self.text = text
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
    for edge_type, words in word.edges.items():
        words.sort(key=(lambda x: x.word_no))
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

def delete_edges(word, labels_to_del):
    edges2 = defaultdict(list)
    for label, value in word.edges.items():
        if label not in labels_to_del:
            edges2[label] = value
    word.edges = edges2

    word.word_strs = {word.text}
    left_word_objs = []
    right_word_objs = []

    sorted_words = sorted(word.children_iter(), key=(lambda x: x.word_no))
    for word2 in sorted_words:
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

    def __str__(self):
        return self.__class__.__name__ + '()'
    def __repr__(self):
        return str(self)

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

def get_names(dobj_word, include_others, errlist):

    def is_name_word(x):
        return x.pos == 'NNP' or (include_others and x.text in ('turtle', 'everyone'))

    name_words = []
    if 'cc' in dobj_word.edges and 'conj' in dobj_word.edges:
        if [w.text for w in dobj_word.edges['cc']] != ['and']:
            errlist.append(BadCCCE(dobj_word, objtype='Turtle names', cc='and'))
    and_names = [dobj_word] + dobj_word.edges['conj']
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
            errlist.append(BadDataCE(dobj_word, param='name', value=name.text))
    return final_names

class MakeCSR(CSR):

    actions = {
        'make': 'create',
        'create': 'create',
        'build': 'create',
        'spawn': 'create',
        'destroy': 'destroy',
        'remove': 'destroy',
        'kill': 'destroy',
    }

    def detect(self, word, env=None):
        """
        Examples:
        Make a turtle named Manish.
        Make turtles named Manish and Eklavya.
        Make Manish.
        Make Manish and Eklavya.
        Make turtles Manish and Eklavya.
        """
        action_words = [word for word in word.word_objs if word.text.lower() in self.actions and word.pos == 'VB']
        proper_nouns = [word for word in word.word_objs if word.pos == 'NNP']

        """
        if len(action_words) > 1:
            debugp('warning: MoveCSR: Multiple action words detected in phrase:\n{}'.format(word.phrase))
        """

        if len(action_words) != 1:
            return None

        action_word = action_words[0]

        params = {}
        errlist = []
        params["action"] = self.actions[action_word.text.lower()]

        dobj_words = action_word.get(['dobj'])
        if len(dobj_words) == 0:
            raise CEList([MissingDataCE(word, param='direct object')])
        elif len(dobj_words) > 1:
            errlist.append(TooManyValuesCE(word, param='direct object'))
        dobj_word = dobj_words[0]

        dobj_dets = [x.text for x in dobj_word.get(['det'])]
        acl_xcomp_roots = dobj_word.get(['acl', 'xcomp'])
        if acl_xcomp_roots:
            name_words = get_names(acl_xcomp_roots[0], params["action"] != 'create', errlist)
        else:
            name_words = []

        def check_acl_xcomp_roots():
            if len(acl_xcomp_roots) == 0:
                raise CEList([MissingDataCE(dobj_word, param='names')])
            elif len(acl_xcomp_roots) > 1:
                errlist.append(TooManyValuesCE(dobj_word, param='names'))

        if dobj_word.text == 'turtles':
            check_acl_xcomp_roots()
        elif dobj_word.text == 'turtle':
            if params["action"] == 'create':
                if dobj_dets == ['a'] or dobj_dets == []:
                    check_acl_xcomp_roots()
                else:
                    errlist.append(BadDataCE(dobj_word, param='turtle determinant', value=dobj_dets[0]))
            else:
                if dobj_dets == ['the']:
                    if len(acl_xcomp_roots) > 0:
                        check_acl_xcomp_roots()
                    else:
                        name_words = [dobj_word]
                elif dobj_dets == []:
                    check_acl_xcomp_roots()
                else:
                    errlist.append(BadDataCE(dobj_word, param='turtle determinant', value=dobj_dets[0]))
            if len(name_words) > 1:
                errlist.append(TooManyValuesCE(dobj_word, param='names'))
            elif len(name_words) == 0:
                errlist.append(MissingDataCE(dobj_word, param='names'))
        else:
            name_words = get_names(dobj_word, params["action"] != 'create', errlist)

        params["names"] = [name_word.text.lower() for name_word in name_words]

        if errlist:
            raise CEList(errlist)
        return params

    def apply(self, word, params, env=None):
        action = params["action"]
        names = params["names"]
        if action == 'destroy' and 'everyone' in names:
            output = ['destroy everyone']
        else:
            output = [' '.join([action, name]) for name in names]
        return output

class MoveCSR(CSR):

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
        'turn': 'turn',
        'rotate': 'turn',
    }

    def detect(self, word, env=None):
        """
        A phrase is roughly a movement command if:
        1. It has the word 'move', 'turn', etc and that is a verb.
        2. It has the word 'forward' or 'backward' or 'upward' etc.
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

        """
        if len(action_words) > 1:
            debugp('warning: MoveCSR: Multiple action words detected in phrase:\n{}'.format(word.phrase))
        """

        if not (len(action_words) == 1 and len(unit_words) == 1):
            return None

        action_word = action_words[0]
        unit_word = unit_words[0]

        params = {}
        errlist = []
        params["action"] = self.actions[action_word.text.lower()]
        params["unit"] = self.units[unit_word.text]

        try:
            params["amount"] = unit_word.get(['nummod'])[0].text
        except IndexError:
            return None

        if len(direction_words) == 0:
            errlist.append(MissingDataCE(word, param='direction'))
        elif len(direction_words) > 1:
            errlist.append(TooManyValues(word, param='direction'))
        else:
            params["direction"] = self.directions[direction_words[0].text]

        dobj_words = action_word.get(['dobj'])
        if len(dobj_words) == 0:
            raise CEList([MissingDataCE(word, param='direct object')])
        elif len(dobj_words) > 1:
            errlist.append(TooManyValuesCE(word, param='direct object'))
        name_words = get_names(dobj_words[0], True, errlist)
        params["names"] = [name_word.text.lower() for name_word in name_words]

        if errlist:
            raise CEList(errlist)
        return params

    def apply(self, word, params, env=None):
        raw_amount = params["amount"]
        try:
            amount = float(raw_amount)
        except ValueError:
            raise CEList([BadDataCE(word, param='number', value=raw_amount)])

        action = params["action"]
        unit = params["unit"]
        direction = params["direction"]
        names = params["names"]

        errlist = []
        if action == 'move':
            if unit != 'pixel':
                errlist.append(BadDataCE(word, param='movement unit', value=unit))
            if direction in ['fd', 'bk', 'up', 'down']:
                output = [' '.join([direction, name, str(amount)]) for name in names]
            elif direction == 'left':
                output = [' '.join(['shl', name, str(amount)]) for name in names]
            elif direction == 'right':
                output = [' '.join(['shr', name, str(amount)]) for name in names]
            else:
                errlist.append(BadDataCE(word, param='movement direction', value=direction))
        elif action == 'turn':
            if unit in ['deg', 'rad']:
                output = [' '.join([unit, name]) for name in names]
                if direction == 'left':
                    output += [' '.join(['rol', name, str(amount)]) for name in names]
                elif direction == 'right':
                    output += [' '.join(['ror', name, str(amount)]) for name in names]
                else:
                    errlist.append(BadDataCE(word, param='rotational direction', value=direction))
            else:
                errlist.append(BadDataCE(word, param='rotational unit', value=unit))

        if errlist:
            raise CEList(errlist)
        else:
            return output

class AndCSR(CSR):

    def detect(self, word, env=None):
        conj_words = word.get(['conj'])
        cc_words = word.get(['cc'])
        if (conj_words and not cc_words) or (not conj_words and cc_words):
            err = CompileError(word, errcode='CONJCC', message=errmsg)
            err.message = "'conj' and 'cc' should either both be present or both be absent."
            raise CEList([err])
        if not (conj_words and cc_words):
            return None
        for x in cc_words:
            if x.text != 'and':
                raise CEList([BadDataCE(word, param='cc', value=x.text)])

        conj_words = word.get(['conj'])
        delete_edges(word, ['conj', 'cc'])
        parts = [word] + conj_words

        stack = []
        output = []
        for word in reversed(parts):
            if word.text.lower() in ('do', 'repeat'):
                output.append('end')
                times_words = [x for x in word.word_objs if x.text == 'times']
                if len(times_words) > 1:
                    raise CEList([TooManyOccsCE(word, text='times')])
                elif len(times_words) == 1:
                    try:
                        amount_str = times_words[0].get(['nummod'])[0].text
                    except IndexError:
                        raise CEList([MissingDataCE(word, param='loop repetitions')])
                    try:
                        amount = int(amount_str)
                    except ValueError:
                        raise CEList([BadDataCE(word, param='loop repetitions', value=amount_str)])
                    stack.append(amount)
                else:
                    if 'once' in word.word_strs:
                        stack.append(1)
                    elif 'twice' in word.word_strs:
                        stack.append(2)
                    elif 'thrice' in word.word_strs:
                        stack.append(3)
                    else:
                        raise CEList([MissingDataCE(word, param='loop repetitions')])
            else:
                output.append(word)

        output = ['repeat {}'.format(x) for x in stack] + list(reversed(output))
        return output

    def apply(self, word, params, env=None):
        output_list = [convert(part) if isinstance(part, Word) else [part] for part in params]
        return list(itertools.chain.from_iterable(output_list))

terminal_CSRs = [MakeCSR(), MoveCSR()]
nonterminal_CSRs = [AndCSR()]

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
        raise CEList([ManyCSRCE(word, list(csr_params.keys()))])
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
        raise CEList([NoCSRCE(word)])
    else:
        return output

def convert_text(text, server_url):
    sentences = parse_text(text, server_url)
    return list(itertools.chain.from_iterable((convert(s) for s in sentences)))

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
                except CEList as e:
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
    group.add_argument('-d2', '--debug2', action='store_true', default=False,
        help='Debugging: View turtle output interactively.')
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
    elif args.debug2:
        if args.source is not None:
            print("Error: Source file should not be specified while debugging", file=sys.stderr)
        else:
            try:
                while True:
                    line = input('debug> ')
                    if line:
                        output = convert_text(line, args.server)
                        for x in output:
                            print(x)
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
