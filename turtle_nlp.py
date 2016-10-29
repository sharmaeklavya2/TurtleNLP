#!/usr/bin/env python3

import requests
import json
import sys
from collections import OrderedDict

BASE_URL = 'http://localhost:9000/'

def debugp(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class EdgeFollowError(KeyError): pass
class EdgeExistsError(Exception): pass

class CompileError(Exception):

    def __init__(self, phrase, messages):
        self.phrase = phrase
        self.messages = messages
        self.message = 'In phrase: {}\n\t{}'.format(
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
        self.edges = {} # keys are edge labels, values are words pointed by edges
        self.word_strs = set()  # type: Set[str] # set of words in phrase
        self.word_objs = [] # type: List[Word] # ordered list of words in phrase

    def __str__(self):
        return 'Word({}, word_no={}, pos={})'.format(self.text, self.word_no, self.pos)
    def __repr__(self):
        return str(self)

    def add_edge(self, edge_type, word):
        # type: (str, Word) -> None
        if edge_type in self.edges:
            raise EdgeExistsError('edge type {} is already present in word {}'.format(edge_type, self.text))
        else:
            self.edges[edge_type] = word

    def get(self, edge_seq, throw=True):
        # type: (Iterable[str]) -> Word
        word = self
        for edge in edge_seq:
            try:
                word = word.edges[edge]
            except KeyError:
                if throw:
                    raise EdgeFollowError('{}.get({}) failed'.format(self, edge_seq))
                else:
                    return None
        return word

def print_preorder(word, edge_type='root', indent=0, file=sys.stdout):
    print('{}{}: {}, {}'.format('  '*indent, edge_type, repr(word.text), repr(word.phrase)), file=file)
    for edge_type2, word2 in sorted(word.edges.items(), key=(lambda x: x[1].word_no)):
        print_preorder(word2, edge_type2, indent + 1)

def find_phrase(word):
    word.word_strs = {word.text}
    left_word_objs = []
    right_word_objs = []
    sorted_words = sorted(word.edges.values(), key=(lambda x: x.word_no))
    for word2 in sorted_words:
        find_phrase(word2)
        if word2.word_no < word.word_no:
            left_word_objs += word2.word_objs
        else:
            right_word_objs += word2.word_objs
        word.word_strs |= word2.word_strs
    word.word_objs = left_word_objs + [word] + right_word_objs
    word.phrase = ' '.join([w.text for w in word.word_objs])

def parse_text(text):

    params = {'properties': "{'annotators': 'pos,depparse', 'outputFormat': 'json'}"}

    debugp('Request sent')
    r = requests.post(BASE_URL, params=params, data=text)

    debugp('Status: {}\n'.format(r.status_code))
#   debugp(r.text)
#   debugp(json.dumps(json.loads(r.text), indent=2))

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
        Output python code for this CSR for the phrase represented by word.
        Raise a CompilerError exception with error messages for the user if needed.
        """
        pass

class MoveCSR(CSR):

    directions = {'ahead': 'forward',
        'forward': 'forward',
        'forwards': 'forward',
        'backward': 'backward',
        'backwards': 'backward',
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
        'degree': 'degree',
        'degrees': 'degree',
        'radian': 'radian',
        'radians': 'radian',
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
        name_words = [word for word in word.word_objs if word.pos == 'NNP']
        direction_words = [word for word in word.word_objs if word.text in self.directions]
        unit_words = [word for word in word.word_objs if word.text in self.units]

        debugp('MoveCSR: {}:'.format(repr(word.phrase)))
        debugp('\taction_words={}'.format(action_words))
        debugp('\tname_words={}'.format(name_words))
        debugp('\tdirection_words={}'.format(direction_words))
        debugp('\tunit_words={}'.format(unit_words))

        if len(action_words) > 1:
            debugp('warning: MoveCSR: Multiple action words detected in phrase:\n{}'.format(word.phrase))

        if not (len(action_words) == 1 and len(name_words) == 1 and len(direction_words) == 1 and len(unit_words) == 1):
            return None

        action_word = action_words[0]
        name_word = name_words[0]
        direction_word = direction_words[0]
        unit_word = unit_words[0]

        params = {}
        try:
            params["action"] = self.actions[action_word.text.lower()]
            params["unit"] = self.units[unit_word.text]
            params["direction"] = self.directions[direction_word.text]
            params["name"] = name_word.text.lower()
            params["amount"] = unit_word.get(['nummod']).text
            return params
        except EdgeFollowError:
            return None

    def apply(self, word, params, env=None):
        raw_amount = params["amount"]
        try:
            amount = float(raw_amount)
        except ValueError:
            raise CompilerError(word.phrase, ['{} is not a valid number.'.format(repr(raw_amount))])

        action = params["action"]
        unit = params["unit"]
        direction = params["direction"]
        name = params["name"]

        errmsgs = []
        if action == 'move':
            if unit != 'pixel':
                unit_errmsg = 'Incorrect unit {} for action {}.'.format(
                    repr(unit_word.text), repr(action_word.text))
                errmsgs.append(unit_errmsg)
            if direction in ['forward', 'backward']:
                output = '{}.{}({})'.format(name, direction, amount)
            else:
                if amount > 0:
                    amount_to_add = '+ ' + str(amount)
                    amount_to_sub = '- ' + str(amount)
                elif amount < 0:
                    amount_to_add = '- ' + str(-amount)
                    amount_to_sub = '+ ' + str(-amount)
                else:
                    amount_to_add = ''
                    amount_to_sub = ''
                if direction == 'up':
                    output = '{name}.sety({name}.ycor{a2a})'.format(name=name, a2a=amount_to_add)
                elif direction == 'down':
                    output = '{name}.sety({name}.ycor{a2s})'.format(name=name, a2s=amount_to_sub)
                if direction == 'right':
                    output = '{name}.setx({name}.xcor{a2a})'.format(name=name, a2a=amount_to_add)
                elif direction == 'left':
                    output = '{name}.setx({name}.xcor{a2s})'.format(name=name, a2s=amount_to_sub)
                else:
                    dir_errmsg = 'Incorrect direction {} for this action {}.'.format(
                        repr(direction_word.text), repr(action_word.text))
                    errmsgs.append(direrrmsg)
        elif action == 'turn':
            if unit in ['degree', 'radian']:
                output = '{name}.{unit}s(); {name}.{direction}({amount})'.format(
                    name=name, unit=unit, direction=direction, amount=amount)
            else:
                unit_errmsg = 'Incorrect unit {} for action {}.'.format(
                    repr(unit_word.text), repr(action_word.text))
                errmsgs.append(unit_errmsg)

        if errmsgs:
            raise CompileError(word.phrase, errmsgs)
        else:
            return output

terminal_CSRs = [MoveCSR()]
nonterminal_CSRs = []

def apply_csrs(word, csr_list):
    csr_params = {}
    for csr in csr_list:
        params = csr.detect(word)
        if params is not None:
            csr_params[csr] = params
    if len(csr_params) > 1:
        raise CompileError(word.phrase, "Multiple CSRs required: " + [str(csr) for csr in csr_params])
    elif len(csr_params) == 1:
        csr, params = list(csr_params.items())[0]
        output = csr.apply(word, params)
        return output
    else:
        return None

def convert(word):
    return apply_csrs(word, nonterminal_CSRs) or apply_csrs(word, terminal_CSRs)

def main():
    sentences = parse_text(input())
    for s in sentences:
        output = convert(s)
        print(output)

if __name__ == '__main__':
    main()
