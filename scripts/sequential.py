"""
Subsequential determinization (Mohri) of a functional transducer, written
out explicitly so that it can stop with an error instead of running out of
memory when the function needs an unbounded look-ahead.

The result is a plain Python structure, easy to export to Ada:

    SequentialTransducer.transitions[state][input_code] = (next_state, output)
    SequentialTransducer.final_output[state] = output (only for final states)
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple

import pynini

EPSILON = 0


class NotSequential(Exception):
    pass


@dataclass
class SequentialTransducer:
    transitions: Dict[int, Dict[int, Tuple[int, str]]] = field(default_factory=dict)
    final_output: Dict[int, str] = field(default_factory=dict)
    start: int = 0

    def number_of_states(self) -> int:
        return len(self.transitions)

    def apply(self, text: str) -> str:
        state, result = self.start, []
        for character in text:
            step = self.transitions[state].get(ord(character))
            if step is None:
                raise KeyError(f"no transition for {character!r} in {text!r}")
            state, output = step
            result.append(output)
        if state not in self.final_output:
            raise KeyError(f"{text!r} is not accepted")
        result.append(self.final_output[state])
        return "".join(result)


def _common_prefix(strings):
    strings = list(strings)
    first = min(strings)
    last = max(strings)
    length = 0
    while length < len(first) and first[length] == last[length]:
        length += 1
    return first[:length]


def _arcs(fst: pynini.Fst):
    table = []
    for state in range(fst.num_states()):
        table.append([(arc.ilabel, arc.olabel, arc.nextstate) for arc in fst.arcs(state)])
    return table


def determinize(fst: pynini.Fst, maximal_residual: int = 24,
                maximal_states: int = 200000) -> SequentialTransducer:
    fst = fst.copy()
    fst.connect()
    arcs = _arcs(fst)
    zero = pynini.Weight.zero(fst.weight_type())
    is_final = [fst.final(state) != zero for state in range(fst.num_states())]

    def closure(subset):
        """Follow epsilon-input arcs; subset is {state: residual}."""
        result = {}
        stack = list(subset.items())
        while stack:
            state, residual = stack.pop()
            if state in result:
                if result[state] != residual:
                    raise NotSequential("ambiguous epsilon output (not functional?)")
                continue
            result[state] = residual
            for input_label, output_label, target in arcs[state]:
                if input_label == EPSILON:
                    output = chr(output_label) if output_label else ""
                    stack.append((target, residual + output))
        return result

    def key(subset):
        return tuple(sorted(subset.items()))

    result = SequentialTransducer()
    start = closure({fst.start(): ""})
    numbers = {key(start): 0}
    pending = [start]
    while pending:
        subset = pending.pop()
        number = numbers[key(subset)]
        result.transitions[number] = {}
        finals = {residual for state, residual in subset.items() if is_final[state]}
        if len(finals) > 1:
            raise NotSequential(f"different final outputs {finals}")
        if finals:
            result.final_output[number] = finals.pop()

        by_label: Dict[int, Dict[int, str]] = {}
        for state, residual in subset.items():
            for input_label, output_label, target in arcs[state]:
                if input_label == EPSILON:
                    continue
                output = residual + (chr(output_label) if output_label else "")
                targets = by_label.setdefault(input_label, {})
                if target in targets and targets[target] != output:
                    raise NotSequential("same input, same state, different outputs")
                targets[target] = output
        for label, targets in by_label.items():
            # Extend each residual through the epsilon closure first, then
            # emit what all hypotheses agree on.
            next_subset = {}
            for target, output in targets.items():
                for state, residual in closure({target: output}).items():
                    if state in next_subset and next_subset[state] != residual:
                        raise NotSequential("not functional")
                    next_subset[state] = residual
            prefix = _common_prefix(next_subset.values())
            next_subset = {state: residual[len(prefix):] for state, residual in next_subset.items()}
            if max(len(residual) for residual in next_subset.values()) > maximal_residual:
                raise NotSequential("look-ahead longer than "
                                    f"{maximal_residual} characters is needed")
            next_key = key(next_subset)
            if next_key not in numbers:
                if len(numbers) >= maximal_states:
                    raise NotSequential(f"more than {maximal_states} states")
                numbers[next_key] = len(numbers)
                pending.append(next_subset)
            result.transitions[number][label] = (numbers[next_key], prefix)
    return result
