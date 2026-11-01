# ipa_uk.ipa as a pipeline of transducers, in Ada

`ipa_uk.ipa` (https://github.com/lang-uk/ipa-uk) is run *symbolically*:
`ipa_uk.re` is replaced by `SymbolicRegularExpressionModule` and the
function gets a `SymbolicText` instead of a `str`. No patch of
`ipa_uk/__init__.py` is needed:

* every `re.sub` / `str.replace` becomes a transducer that reproduces the
  semantics of Python exactly (leftmost match, backtracking priority of
  greedy `?` and `+`; `([бвгґд])\1` is expanded into alternatives);
* `text.lower()` is the identity: the Ada side lowers the word itself;
* the `while True` loop is driven by `SymbolicText.__eq__`, which answers
  True when no rule of the loop body can match anything the loop produced.

The 196 rules (the voicing loop unrolled 7 times) are merged greedily into
stages. Each stage is a deterministic transducer that reads the word either
from left to right or from right to left; five rules of `ipa` need an
unbounded look-ahead to the right but none to the left, e.g. "only the last
жж" or "move ˈ in front of the whole consonant cluster". Result:

| Stage | Direction | Rules | States |
|---|---|---|---|
| 1 | → | 11 | 27 |
| 2 | ← | 2 | 13 |
| 3 | → | 66 | 281 |
| 4 | ← | 98 | 1164 |
| 5 | → | 4 | 5 |
| 6 | ← | 15 | 2622 |

## Files

* `symbolic_regular_expressions.py`: regex subset parser, `re.sub` to transducer
* `sequential.py`: subsequential determinization that fails instead of hanging
* `build_pipeline.py`: runs `ipa`, builds `pipeline.pickle`
* `generate_ada.py`: writes `ada/source/ukrainian_ipa-tables.ads`
* `compare_with_python.py`, `compare_ada_with_python.py`: checks on ipa-uk/sample
* `ada/`: `Ukrainian_IPA.Transcribe` and the test program `transcribe_words`

## Rebuild

    pip install pynini
    export PYTHONPATH=path/to/ipa-uk:.
    python3 build_pipeline.py          # about 3 minutes, < 2.5 GB
    python3 generate_ada.py ada/source/ukrainian_ipa-tables.ads
    (cd ada && gprbuild -P ukrainian_ipa.gpr)
    python3 compare_ada_with_python.py

## Differences from ipa_uk.ipa

* The voicing loop is computed for consonant clusters of at most 8 symbols
  (`MAXIMAL_CLUSTER_SYMBOLS`); on ipa-uk/sample it never needs more than one
  changing iteration.
* Characters outside the alphabet (letters, `'`, `’`, `-`, U+0301, U+0300)
  make `Transcribe` fail instead of passing through.
* Words longer than `Maximum_Word_Length` (64) fail.

On the 9996 words of ipa-uk/sample and on 50000 random words the Ada
result is identical to `ipa_uk.ipa`.
