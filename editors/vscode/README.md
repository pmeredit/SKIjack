# SKIjack for VS Code

Syntax highlighting for `.ski` files in both lexicons. The grammar follows
`python/skijack/lexicon.py`'s token table, so ASCII and Unicode spellings
of the same token get the same scope.

Install locally by linking this folder into VS Code's extensions directory
and reloading the window:

    ln -s "$(pwd)/editors/vscode" ~/.vscode/extensions/sigilante.skijack-0.1.0

No build step; there is nothing to compile.
