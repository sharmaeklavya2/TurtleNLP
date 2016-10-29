# TurtleNLP

Using Natural Language Processing to interpret English commands given to turtles.

See https://docs.python.org/library/turtle.html for an introduction to turtle graphics in python.

TurtleNLP uses Stanford's typed dependency parser to recoginze control structures.
This work is inspired by
[an IEEE research paper](http://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=7168325&isnumber=7168316).

TurtleNLP is written using python3 and requires [`requests`](http://docs.python-requests.org).

### How to use locally

1.  First set up a local coreNLP server at port 9000.
    Instructions for doing this can be found at http://stanfordnlp.github.io/CoreNLP/corenlp-server.html.

2.  Then run `turtle_nlp.py` and enter your instructions in English.
