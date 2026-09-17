"""The round-trip laws of SYNTAX.md §1 item 4 and DESIDERATA.md item 4.

Rendering need not reproduce whitespace, only an equal tree.
"""

import pytest

from skijack.parser import parse
from skijack.render import render

from conftest import ALL_SOURCES

IDS = [f"{s}.{lx}" for s, lx, _ in ALL_SOURCES]


@pytest.mark.parametrize("stem,lexicon,path", ALL_SOURCES, ids=IDS)
def test_render_in_the_same_lexicon_reparses_equal(stem, lexicon, path):
    src = path.read_text(encoding="utf-8")
    tree = parse(src, lexicon)
    assert parse(render(tree, lexicon), lexicon) == tree


@pytest.mark.parametrize("stem,lexicon,path", ALL_SOURCES, ids=IDS)
def test_cross_lexicon_render_reparses_equal(stem, lexicon, path):
    other = "unicode" if lexicon == "ascii" else "ascii"
    tree = parse(path.read_text(encoding="utf-8"), lexicon)
    assert parse(render(tree, other), other) == tree


@pytest.mark.parametrize("stem,lexicon,path", ALL_SOURCES, ids=IDS)
def test_render_is_idempotent_on_text(stem, lexicon, path):
    tree = parse(path.read_text(encoding="utf-8"), lexicon)
    once = render(tree, lexicon)
    assert render(parse(once, lexicon), lexicon) == once


@pytest.mark.parametrize("stem,lexicon,path", ALL_SOURCES, ids=IDS)
def test_render_round_trips_through_the_other_lexicon(stem, lexicon, path):
    other = "unicode" if lexicon == "ascii" else "ascii"
    tree = parse(path.read_text(encoding="utf-8"), lexicon)
    there = parse(render(tree, other), other)
    back = parse(render(there, lexicon), lexicon)
    assert back == tree
