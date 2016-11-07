#!/usr/bin/env python3

"""
Run tests in JSON format and find out accuracy.
"""

import json
import os
import itertools
import argparse
from collections import defaultdict

from turtle_nlp import CEList
import turtle_nlp

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')

def get_test_files(path):
    # type: () -> List[Tuple[str, str]]
    if os.path.isdir(path):
        paths = []
        for (dirpath, dnames, fnames) in os.walk(path):
            dnames.sort()
            fnames.sort()
            json_files = [os.path.join(dirpath, fname) for fname in fnames if os.path.splitext(fname)[1] == '.json']
            paths += sorted(json_files)
        return paths
    elif os.path.isfile(path):
        return [path]
    else:
        raise Exception("path is neither a file nor a directory.")

class Test:
    fpath = ''
    name = ''
    text = ''
    output = [] # type: List[str] # stores result or errors
    has_errors = False
    params = {} # type: Dict[str, Dict[str, str]]
    weight = 1

    def from_dict(self, fpath, d):
        # type: (str, dict) -> None
        self.fpath = fpath
        self.name = d.get('name', os.path.split(fpath)[1])
        self.text = d['text']
        paramsl = d.get('params', {})
        if 'result' not in d and 'paramsd' in d:
            raise Exception("'paramsd' present without 'result' in {}: {}".format(fpath, self.name))
        paramsd = d.get('paramsd', {})
        self.params = defaultdict(dict)
        for template_param, values_list in paramsl.items():
            for value in values_list:
                self.params[template_param][value] = value.lower()
        for template_param, values_dict in paramsd.items():
            for key, value in values_dict.items():
                self.params[template_param][key] = value
        self.weight = d.get('weight', 1)
        if 'results' in d:
            raise Exception("Change 'results' to 'result' in {}: {}".format(fpath, self.name))
        if 'error' in d:
            raise Exception("Change 'error' to 'errors' in {}: {}".format(fpath, self.name))
        if 'result' in d and 'errors' in d:
            raise Exception("Found both 'result' and 'errors' in {}: {}".format(fpath, self.name))
        elif 'result' not in d and 'errors' not in d:
            raise Exception("Found neither 'result' nor 'errors' in {}: {}".format(fpath, self.name))
        self.has_errors = 'errors' in d
        self.output = d.get('result', sorted(d.get('errors', ())))

    def __init__(self, fpath, test_dict):
        # type: (str, dict) -> None
        self.from_dict(fpath, test_dict)

    def __repr__(self):
        return 'Test({}: {})'.format(self.fpath, self.name)

def get_stats(correct, wrong, indent):
    # type: (int, int, int) -> str
    result_format = 'Pass: {} ({}%), Fail: {} ({}%), Total: {}'
    total = correct + wrong
    correct_percent = str(100 * correct / total)[:5]
    wrong_percent = str(100 * wrong / total)[:5]
    indent_str = '\t' * indent
    return indent_str + result_format.format(correct, correct_percent, wrong, wrong_percent, total)
    
def run_all_tests(path, print_failures, server_url):
    # type: (str, bool, str) -> None
    fpaths = get_test_files(path)
    tot_correct = 0
    tot_wrong = 0
    for fpath in fpaths:
        with open(fpath) as fobj:
            test = Test(fpath, json.load(fobj))
        print(test.fpath)
        correct, wrong = run_test(test, print_failures, server_url)
        tot_correct += correct
        tot_wrong += wrong
        if wrong:
            print(get_stats(correct, wrong, 1))
    print('\n' + get_stats(tot_correct, tot_wrong, 0))

def iter_text_output(text_template, output_template, params):
    # type: (str, Dict[str, List[str]]) -> Generator[str, None, None]
    params_as_list = list(params.items())
    template_params = [x[0] for x in params_as_list]
    template_dicts = [list(x[1].items()) for x in params_as_list]
    values_instances = itertools.product(*template_dicts)
    for values_instance in values_instances:
        text_replacements = {k: v for k, v in zip(template_params, [x[0] for x in values_instance])}
        output_replacements = {k: v for k, v in zip(template_params, [x[1] for x in values_instance])}
        text = text_template.format(**text_replacements)
        output = [instr_template.format(**output_replacements) for instr_template in output_template]
        yield (text, output)

def execute_sentence(text, server_url):
    # type: (str, str) -> Tuple[bool, List[str]]
    try:
        return (False, turtle_nlp.convert_text(text, server_url))
    except CEList as e:
        return (True, sorted(e.errcodes))

def run_test(test, print_failures, server_url):
    # type: (Test, bool, str) -> (int, int)
    correct = 0
    wrong = 0
    for text, output in iter_text_output(test.text, test.output, test.params):
        has_errors, nlp_output = execute_sentence(text, server_url)
        if has_errors == test.has_errors:
            if has_errors:
                result = sorted(nlp_output) == sorted(output)
            else:
                result = nlp_output == output
            if result:
                correct += 1
            else:
                wrong += 1
                if print_failures:
                    print('\t' + text)
                    print('\t\texpected:', output)
                    print('\t\treceived:', nlp_output)
        elif has_errors:
            wrong += 1
            if print_failures:
                print('\t' + text)
                print('\t\tGot unexpected errors:', nlp_output)
        else:
            wrong += 1
            if print_failures:
                print('\t' + text)
                print("\t\tExpected errors but didn't get any.")
    if correct + wrong == 0:
        print("No elems in test:", test)
    return (correct, wrong)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default=turtle_nlp.DEFAULT_BASE_URL,
        help='URL of CoreNLP server to connect to.')
    parser.add_argument('path', nargs='?',
        help='Path to file or directory with tests.')
    parser.add_argument('--show-fails', action='store_true', default=False,
        help='Show all sentences which failed tests.')
    args = parser.parse_args()

    path = args.path or TEST_DIR
    run_all_tests(path, args.show_fails, args.server)

if __name__ == '__main__':
    main()
