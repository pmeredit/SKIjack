"""skijack -- a surface language over SKI: step 1 (syntax), step 2
(codegen without types or quotation) and step 3 (the type-generated
forms of the interpreter interface).

See ``../README.md`` for what is implemented and what is not.
"""

from . import ast
from .lexicon import lex_ascii, lex_unicode, TOKEN_TABLE
from .parser import parse, parse_ascii, parse_unicode, ParseError
from .render import render, render_ascii, render_unicode
from .expand import expand_program, Expansion, ExpandError
from .generate import generate, GenerateError
from .probe import Prober, fast_reduce

__version__ = "0.1.0"

__all__ = [
    "ast", "lex_ascii", "lex_unicode", "TOKEN_TABLE",
    "parse", "parse_ascii", "parse_unicode", "ParseError",
    "render", "render_ascii", "render_unicode",
    "expand_program", "Expansion", "ExpandError",
    "generate", "GenerateError",
    "Prober", "fast_reduce", "__version__",
]
