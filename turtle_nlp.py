#!/usr/bin/env python3

import requests
import json
import sys
from collections import OrderedDict

BASE_URL = 'http://localhost:9000/'

class EdgeFollowError(KeyError): pass
class EdgeExistsError(Exception): pass

debugp = print

class Word:
    text = ''
    word_no = None      # Index of word in list of words in sentence
    pos = ''            # Part of speech
    phrase = ''         # Yield in dependency tree

    def __init__(self, text, word_no, pos):
        self.text = text
        self.word_no = word_no
        self.pos = pos
        self.edges = {} # keys are edge labels, values are words pointed by edges
        self.word_strs = set()  # type: Set[str] # set of words in phrase
        self.word_objs = [] # type: List[Word] # ordered list of words in phrase

    def __str__(self):
        return "Word({}, word_no={}, pos={})".format(self.text, self.word_no, self.pos)
    def __repr__(self):
        return str(self)

    def add_edge(self, edge_type, word):
        # type: (str, Word) -> None
        if edge_type in self.edges:
            raise EdgeExistsError("edge type {} is already present in word {}".format(edge_type, self.text))
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
                    raise EdgeFollowError("{}.get({}) failed".format(self, edge_seq))
                else:
                    return None
        return word

def print_preorder(word, edge_type='root', indent=0):
    print('{}{}: {}, {}'.format('  '*indent, edge_type, repr(word.text), repr(word.phrase)))
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

    params = {'properties': '{"annotators": "pos,depparse", "outputFormat": "json"}'}

    print("Request sent", file=sys.stderr)
    r = requests.post(BASE_URL, params=params, data=text)

    print("Status: {}\n".format(r.status_code), file=sys.stderr)
#   print(r.text)
#   print(json.dumps(json.loads(r.text), indent=2))

    return [parse_sentence(sentence, text) for sentence in r.json()["sentences"]]

def parse_sentence(sentence, text):
    """Analyzes a JSON sentence and returns the root word object"""
    words_list = []
    words_dict = OrderedDict()
    least_index = 1<<30
    highest_index = 0
    for token in sentence["tokens"]:
        word = Word(token["word"], token["index"], token["pos"])
        words_list.append(word)
        words_dict[token["word"]] = word
        least_index = min(least_index, token["characterOffsetBegin"])
        highest_index = max(highest_index, token["characterOffsetEnd"])

    root = None
    for edge in sentence["basic-dependencies"]:
        governor_index = edge["governor"]
        dependent = words_list[edge["dependent"] - 1]
        edge_type = edge["dep"]
        if governor_index == 0:
            root = dependent
        else:
            governor = words_list[governor_index - 1]
            governor.add_edge(edge_type, dependent)

    find_phrase(root)
    return root


class CSR:
    def detect(self, word):
        return None

class MoveCSR:

    directions = ['forwards', 'backwards', 'upwards', 'downwards', 'leftwards', 'rightwards',
        'up', 'down', 'left', 'right', 'clockwise', 'anticlockwise']
    units = ['units', 'pixels', 'meters', 'degrees', 'radians']
    actions = ['move', 'shift', 'turn', 'rotate']

    def detect(self, word):
        """
        A phrase is roughly a movement command if:
        1. It has the word 'move', 'turn', etc and that is a verb.
        2. There is a proper noun in the phrase (which is the name of the turtle).
        4. It has the word 'forward' or 'backward' or 'upward' etc.
        3. It has the word 'units' or 'pixels' with a number adjoining it.
        """
        action_words = [word for word in word.word_objs if (word.text.lower() in MoveCSR.actions and word.pos == 'VB')]
        name_words = [word for word in word.word_objs if word.pos == 'NNP']
        direction_words = [word for word in word.word_objs
            if (word.text in self.directions or word.text+'s' in self.directions)]
        unit_words = [word for word in word.word_objs
            if (word.text in self.units or word.text+'s' in self.units)]

        debugp("action_words={}\nname_words={}\ndirection_words={}\nunit_words={}".format(
            action_words, name_words, direction_words, unit_words))
        if not (len(action_words) == 1 and len(name_words) == 1 and len(direction_words) == 1 and len(unit_words) == 1):
            return None
        action_word = action_words[0]
        name_word = name_words[0]
        direction_word = direction_words[0]
        unit_word = unit_words[0]

        if len(action_words) > 1:
            debugp("Multiple action words detected in phrase:\n{}".format(word.phrase), file=sys.stderr)

        parameters = {}
        try:
            parameters["action"] = action_word.text.lower()
            parameters["unit"] = unit_word.text.strip('s')
            parameters["amount"] = unit_word.get(['nummod']).text
            parameters["direction"] = direction_word.text.strip('s')
            parameters["name"] = name_word.text
            return parameters
        except EdgeFollowError:
            return None

def main():
    sentences = parse_text(input())
    for s in sentences:
        print(repr(s.phrase))
        print_preorder(s)
        print()
        print(MoveCSR().detect(s))

if __name__ == "__main__":
    main()
