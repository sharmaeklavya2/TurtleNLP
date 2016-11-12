# TurtleNLP

Using Natural Language Processing to interpret English commands given to turtles.

See https://docs.python.org/library/turtle.html for an introduction to turtle graphics in python.

TurtleNLP uses Stanford's typed dependency parser to recoginze control structures.
This work is inspired by
[an IEEE research paper](http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7168325&isnumber=7168316).

TurtleNLP is written using python3 and requires [`requests`](http://docs.python-requests.org).

### How it works

1.  Text in natural language is passed to a coreNLP server.
    The coreNLP server gives a JSON response.
    The response contains Part-of-Speech tokens of all words
    and list of edges in the typed dependency graph of each sentence.

2.  The Control Structure Recognizer written by us (in `turtle_nlp.py`)
    uses the typed dependency graph to understand the sentence and emit 'tortuga' code.

    Tortuga is an intermediate language designed by us for expressing turtle manipulation commands.
    Tortuga is easy for humans to read and write and easy for machines to parse.
    See `inpr.py` to see the list of commands supported by tortuga.

3.  A tortuga interpreter (`inpr.py`) executes tortuga code using python's `turtle` module.

### How to run it locally

1.  First set up a local coreNLP server at port 9000.
    Instructions for doing this can be found at http://stanfordnlp.github.io/CoreNLP/corenlp-server.html.

2.  Download and install `requests`, if you don't have it already.

3.  Run `turtle_nlp.py` and enter your instructions in English.
    For e.g., `Move the turtle forward by 30 units.`

### Examples

These examples contain English sentences and tortuga code generated for them.

* Move the turtle forward by 30 units.

  ```
  fd turtle 30.0
  ```

* Move the turtle 40 units up.

  ```
  up turtle 40.0
  ```

* Create a turtle named Monty and rotate Monty by 90 degrees in the anticlockwise direction.

  ```
  create monty
  deg monty
  rol monty 90.0
  ```

* Move Monty forward by 100 units, turn Monty 90 degrees towards left and do this 4 times.

  ```
  repeat 4
  fd monty 100.0
  deg monty
  rol monty 90.0
  end
  ```

### Testing

Automated tests can be run using `run_tests.py`.
`run_tests.py` runs TurtleNLP on many sentences and reports the accuracy.
