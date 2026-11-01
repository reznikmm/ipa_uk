"""
Runs ipa_uk.ipa symbolically and turns its rewrite rules into a short
pipeline of deterministic transducers (stages).

A stage reads its input either from left to right, streaming, or from
right to left: then it needs the whole word first. Neighbouring rules are
merged into one stage as long as the merged transducer stays deterministic
in the stage's direction and below a state budget.
"""

import pickle
import sys
import time
from dataclasses import dataclass
from typing import List

import pynini

import ipa_uk
import sequential
import symbolic_regular_expressions as symbolic

ACUTE = "\u0301"
GRAVE = "\u0300"
LOWERCASE_LETTERS = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
OTHER_CHARACTERS = "’'-"

# The voicing loop "while True" of ipa() iterates until nothing changes.
# On strings with arbitrarily long consonant clusters that never happens,
# so the loop is computed for clusters of at most this many symbols
# (on ipa-uk/sample the loop never changes a word more than once).
MAXIMAL_CLUSTER_SYMBOLS = 8
CLUSTER_SYMBOLS = set("pbtdszʃʒkɡxɦfvʲː\u0361")

STATE_BUDGET = 3000
MAXIMAL_RESIDUAL = 24


@dataclass
class Stage:
    direction: str  # "left to right" or "right to left"
    rules: List[str]
    transducer: sequential.SequentialTransducer


def input_alphabet():
    return set(LOWERCASE_LETTERS + OTHER_CHARACTERS + ACUTE + GRAVE)


def bounded_cluster_strings(alphabet):
    fst = pynini.Fst()
    one = pynini.Weight.one(fst.weight_type())
    states = [fst.add_state() for _ in range(MAXIMAL_CLUSTER_SYMBOLS + 1)]
    fst.set_start(states[0])
    for run, state in enumerate(states):
        fst.set_final(state)
        for character in alphabet:
            if character not in CLUSTER_SYMBOLS:
                fst.add_arc(state, pynini.Arc(ord(character), ord(character), one, states[0]))
            elif run < MAXIMAL_CLUSTER_SYMBOLS:
                fst.add_arc(state, pynini.Arc(ord(character), ord(character), one,
                                              states[run + 1]))
    return fst


def collect_rules():
    alphabet_in = input_alphabet()
    collector = symbolic.Builder(alphabet_in, set(), None, collect_only=True)
    ipa_uk.re = symbolic.SymbolicRegularExpressionModule(collector)
    ipa_uk.ipa(symbolic.SymbolicText(collector), check_accent=False)
    alphabet = alphabet_in | collector.literals_seen

    builder = symbolic.Builder(alphabet_in, alphabet, bounded_cluster_strings(alphabet))
    ipa_uk.re = symbolic.SymbolicRegularExpressionModule(builder)
    result = ipa_uk.ipa(symbolic.SymbolicText(builder), check_accent=False)
    return [rule for rule in result.rules if rule is not None], alphabet


def determinize(fst, direction):
    if direction == "right to left":
        fst = pynini.reverse(fst)
    return sequential.determinize(fst, maximal_residual=MAXIMAL_RESIDUAL,
                                  maximal_states=STATE_BUDGET)


def other_direction(direction):
    return "right to left" if direction == "left to right" else "left to right"


def other_direction(direction):
    return "right to left" if direction == "left to right" else "left to right"


def output_symbols(transducer: sequential.SequentialTransducer):
    symbols = set()
    for row in transducer.transitions.values():
        for _, output in row.values():
            symbols |= set(output)
    for output in transducer.final_output.values():
        symbols |= set(output)
    return symbols


def build_pipeline(rules, alphabet_in) -> List[Stage]:
    stages: List[Stage] = []
    symbols = alphabet_in
    index = 0
    while index < len(rules):
        domain = symbolic.symbol_set_star({ord(c) for c in symbols})
        group = pynini.compose(domain, rules[index].transducer).optimize()
        stage = None
        for direction in ("left to right", "right to left"):
            try:
                stage = Stage(direction, [rules[index].description], determinize(group, direction))
                break
            except sequential.NotSequential:
                pass
        if stage is None:
            raise RuntimeError("neither direction works for " + rules[index].description)
        index += 1
        while index < len(rules):
            candidate = pynini.compose(group, rules[index].transducer).optimize()
            transducer = None
            for direction in (stage.direction, other_direction(stage.direction)):
                try:
                    transducer = determinize(candidate, direction)
                    stage.direction = direction
                    break
                except sequential.NotSequential:
                    pass
            if transducer is None:
                break
            group = candidate
            stage.transducer = transducer
            stage.rules.append(rules[index].description)
            index += 1
        print(f"stage {len(stages) + 1}: {stage.direction}, {len(stage.rules)} rules, "
              f"{stage.transducer.number_of_states()} states", file=sys.stderr, flush=True)
        stages.append(stage)
        symbols = output_symbols(stage.transducer)
    return stages


def apply_pipeline(stages: List[Stage], word: str) -> str:
    for stage in stages:
        if stage.direction == "left to right":
            word = stage.transducer.apply(word)
        else:
            word = stage.transducer.apply(word[::-1])[::-1]
    return word


if __name__ == "__main__":
    started = time.time()
    rules, alphabet = collect_rules()
    print(f"{len(rules)} rules, alphabet of {len(alphabet)}, "
          f"{time.time() - started:.0f} s", file=sys.stderr, flush=True)
    stages = build_pipeline(rules, input_alphabet())
    print(f"pipeline built in {time.time() - started:.0f} s", file=sys.stderr)
    with open("pipeline.pickle", "wb") as file:
        pickle.dump(stages, file)
