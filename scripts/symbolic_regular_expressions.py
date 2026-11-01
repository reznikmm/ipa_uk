"""
Turns every re.sub call made by ipa_uk.ipa into a finite state transducer.

ipa_uk.ipa looks up the name "re" in its module globals on every call, so
we do not patch the file at all: we put SymbolicRegularExpressionModule into
ipa_uk.re and call ipa_uk.ipa with a SymbolicText instead of a str.
Every re.sub (and str.replace / str.lower) on a SymbolicText becomes one
transducer that reproduces the semantics of Python's re.sub exactly:

  * scanning from left to right, a match is taken at the leftmost position
    where one exists, scanning resumes after it;
  * among the matches that start at the same position the one that the
    backtracking matcher finds first wins (greedy ?, +).

Both conditions are written as regular "no better choice was possible"
constraints over the input string annotated with marker symbols.

The "while True" loop needs no patch either: SymbolicText.__eq__ answers
True as soon as no rewrite of the loop body can match anything the loop
produced so far, i.e. one more iteration is the identity.
"""

import re as python_regular_expressions
import string
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import pynini

EPSILON = 0
COPY_MARKER = 0xE000
FIRST_ALTERNATIVE_MARKER = 0xE001


# --------------------------------------------------------------------------
# Small helpers to build automata over code point labels
# --------------------------------------------------------------------------

def _one(fst: pynini.Fst):
    return pynini.Weight.one(fst.weight_type())


def _add_arc(fst: pynini.Fst, source: int, input_label: int, output_label: int, target: int):
    fst.add_arc(source, pynini.Arc(input_label, output_label, _one(fst), target))


def symbol_set_acceptor(labels) -> pynini.Fst:
    """Acceptor of exactly one symbol from the set."""
    fst = pynini.Fst()
    start = fst.add_state()
    final = fst.add_state()
    fst.set_start(start)
    fst.set_final(final)
    for label in sorted(labels):
        _add_arc(fst, start, label, label, final)
    return fst


def symbol_set_star(labels) -> pynini.Fst:
    fst = pynini.Fst()
    state = fst.add_state()
    fst.set_start(state)
    fst.set_final(state)
    for label in sorted(labels):
        _add_arc(fst, state, label, label, state)
    return fst


def epsilon_acceptor() -> pynini.Fst:
    fst = pynini.Fst()
    state = fst.add_state()
    fst.set_start(state)
    fst.set_final(state)
    return fst


def ignore_markers(acceptor: pynini.Fst, markers) -> pynini.Fst:
    """The same language with any number of markers inserted anywhere."""
    result = acceptor.copy()
    for state in range(result.num_states()):
        for marker in markers:
            _add_arc(result, state, marker, marker, state)
    return result


def labels_of(text: str) -> List[int]:
    return [ord(character) for character in text]


# --------------------------------------------------------------------------
# Parsing of the small regular expression subset used by ipa_uk
# --------------------------------------------------------------------------

@dataclass
class CharacterSet:
    characters: Set[str]
    negated: bool = False
    any_character: bool = False
    back_reference: Optional[int] = None

    def resolve(self, alphabet: Set[str]) -> Set[str]:
        if self.any_character:
            return alphabet - {"\n"}
        if self.negated:
            return alphabet - self.characters
        return set(self.characters)


@dataclass
class Element:
    character_set: CharacterSet
    quantifier: str  # "1", "?" or "+"
    group: Optional[int]


@dataclass
class Pattern:
    alternatives: List[List[Element]]
    anchored_at_start: bool
    anchored_at_end: bool
    literal_characters: Set[str] = field(default_factory=set)


def parse_pattern(text: str) -> Pattern:
    anchored_at_start = text.startswith("^")
    anchored_at_end = text.endswith("$") and not text.endswith("\\$")
    body = text[1 if anchored_at_start else 0 : len(text) - (1 if anchored_at_end else 0)]
    elements: List[Element] = []
    literal_characters: Set[str] = set()
    current_group: Optional[int] = None
    group_count = 0
    position = 0
    while position < len(body):
        character = body[position]
        if character == "(":
            if current_group is not None:
                raise NotImplementedError("nested groups: " + text)
            group_count += 1
            current_group = group_count
            position += 1
            continue
        if character == ")":
            current_group = None
            position += 1
            if position < len(body) and body[position] in "?+*{":
                raise NotImplementedError("quantified group: " + text)
            continue
        if character == "[":
            closing = body.index("]", position + 2)
            content = body[position + 1 : closing]
            negated = content.startswith("^")
            if negated:
                content = content[1:]
            if "-" in content[1:-1] or "\\" in content:
                raise NotImplementedError("ranges or escapes in a set: " + text)
            character_set = CharacterSet(set(content), negated=negated)
            position = closing + 1
        elif character == ".":
            character_set = CharacterSet(set(), any_character=True)
            position += 1
        elif character == "\\":
            escaped = body[position + 1]
            if escaped.isdigit():
                character_set = CharacterSet(set(), back_reference=int(escaped))
            elif escaped in string.ascii_letters:
                raise NotImplementedError("escape class: " + text)
            else:
                character_set = CharacterSet({escaped})
            position += 2
        elif character in "*{|":
            raise NotImplementedError("unsupported construct: " + text)
        else:
            character_set = CharacterSet({character})
            position += 1
        literal_characters |= character_set.characters
        quantifier = "1"
        if position < len(body) and body[position] in "?+":
            quantifier = body[position]
            position += 1
        elements.append(Element(character_set, quantifier, current_group))

    # A back reference to a one-character group "([abc])\1" is expanded
    # into the alternatives "(a)a", "(b)b", "(c)c".
    alternatives = [elements]
    for index, element in enumerate(elements):
        reference = element.character_set.back_reference
        if reference is None:
            continue
        group_elements = [item for item in elements if item.group == reference]
        if (len(group_elements) != 1 or group_elements[0].quantifier != "1"
                or group_elements[0].character_set.negated
                or group_elements[0].character_set.any_character):
            raise NotImplementedError("back reference to a complex group: " + text)
        group_index = elements.index(group_elements[0])
        expanded = []
        for alternative in alternatives:
            for character in sorted(group_elements[0].character_set.characters):
                copy = list(alternative)
                copy[group_index] = Element(CharacterSet({character}), "1", reference)
                copy[index] = Element(CharacterSet({character}), "1", None)
                expanded.append(copy)
        alternatives = expanded
    return Pattern(alternatives, anchored_at_start, anchored_at_end, literal_characters)


def parse_replacement(text: str, is_template: bool) -> List[Tuple[str, object]]:
    """[("literal", "ab"), ("group", 1), ...]"""
    if not is_template:
        return [("literal", text)]
    parts: List[Tuple[str, object]] = []
    position = 0
    for match in python_regular_expressions.finditer(r"\\(\d)", text):
        parts.append(("literal", text[position : match.start()]))
        parts.append(("group", int(match.group(1))))
        position = match.end()
    parts.append(("literal", text[position:]))
    if "\\" in "".join(value for kind, value in parts if kind == "literal"):
        raise NotImplementedError("unsupported replacement: " + text)
    return parts


# --------------------------------------------------------------------------
# One re.sub as a transducer
# --------------------------------------------------------------------------

class RewriteRule:
    def __init__(self, pattern: Pattern, replacement: List[Tuple[str, object]],
                 alphabet: Set[str], description: str):
        self.pattern = pattern
        self.replacement = replacement
        self.alphabet = alphabet
        self.description = description
        self.sigma = {ord(character) for character in alphabet}
        self.markers: List[int] = [COPY_MARKER]
        self.alternative_constraints: List[Tuple[int, pynini.Fst]] = []
        self.parser = self._build_parser()
        self.transducer = self._build_transducer()

    # Language of the elements alternative[index:] (input side only).
    def _suffix_language(self, alternative: List[Element], index: int) -> pynini.Fst:
        result = epsilon_acceptor()
        for element in alternative[index:]:
            labels = {ord(c) for c in element.character_set.resolve(self.alphabet)}
            one = symbol_set_acceptor(labels)
            if element.quantifier == "?":
                one = pynini.union(one, epsilon_acceptor())
            elif element.quantifier == "+":
                one = pynini.concat(one, pynini.closure(one.copy()))
            result = pynini.concat(result, one)
        return result.optimize()

    def match_language(self) -> pynini.Fst:
        """Strings in which this rule finds at least one match."""
        matches = pynini.union(*[self._suffix_language(alternative, 0)
                                 for alternative in self.pattern.alternatives])
        anything = symbol_set_star(self.sigma)
        before = epsilon_acceptor() if self.pattern.anchored_at_start else anything
        after = epsilon_acceptor() if self.pattern.anchored_at_end else anything.copy()
        return pynini.concat(pynini.concat(before, matches), after).optimize()

    def _new_marker(self, preferred_language: pynini.Fst) -> int:
        marker = FIRST_ALTERNATIVE_MARKER + len(self.alternative_constraints)
        self.markers.append(marker)
        self.alternative_constraints.append((marker, preferred_language))
        return marker

    def _boundary_literals(self, alternative: List[Element]):
        """Which replacement literal is printed at which element boundary,
        and which groups are copied to the output."""
        literals = {0: ""}
        copied_groups = set()
        previous_group = 0
        boundary = 0
        for kind, value in self.replacement:
            if kind == "literal":
                literals[boundary] = literals.get(boundary, "") + value
            else:
                if value <= previous_group:
                    raise NotImplementedError("groups out of order: " + self.description)
                previous_group = value
                copied_groups.add(value)
                last = max(i for i, element in enumerate(alternative) if element.group == value)
                boundary = last + 1
                literals.setdefault(boundary, "")
        return literals, copied_groups

    def _add_output_chain(self, fst, source, text, target):
        labels = labels_of(text)
        if not labels:
            _add_arc(fst, source, EPSILON, EPSILON, target)
            return
        for label in labels[:-1]:
            state = fst.add_state()
            _add_arc(fst, source, EPSILON, label, state)
            source = state
        _add_arc(fst, source, EPSILON, labels[-1], target)

    def _build_parser(self) -> pynini.Fst:
        """Input: annotated input (characters and markers), output: result."""
        pattern = self.pattern
        fst = pynini.Fst()
        main = fst.add_state()
        fst.set_final(main)
        start = main
        if pattern.anchored_at_start:
            start = fst.add_state()
            fst.set_final(start)
        fst.set_start(start)
        end_of_match = main
        if pattern.anchored_at_end:
            end_of_match = fst.add_state()
            fst.set_final(end_of_match)

        for source in {start, main}:
            copy_state = fst.add_state()
            _add_arc(fst, source, COPY_MARKER, EPSILON, copy_state)
            for label in self.sigma:
                _add_arc(fst, copy_state, label, label, main)

        first_sets = [alt[0].character_set.resolve(self.alphabet)
                      for alt in pattern.alternatives]
        for i in range(len(first_sets)):
            for j in range(i + 1, len(first_sets)):
                if first_sets[i] & first_sets[j]:
                    raise NotImplementedError("overlapping alternatives: " + self.description)

        for alternative in pattern.alternatives:
            literals, copied_groups = self._boundary_literals(alternative)
            count = len(alternative)
            before = [fst.add_state() for _ in range(count + 1)]   # before literal
            after = [fst.add_state() for _ in range(count + 1)]    # after literal
            for boundary in range(count + 1):
                self._add_output_chain(fst, before[boundary], literals.get(boundary, ""),
                                       after[boundary])
            _add_arc(fst, start, EPSILON, EPSILON, before[0])
            _add_arc(fst, after[count], EPSILON, EPSILON, end_of_match)
            for index, element in enumerate(alternative):
                labels = {ord(c) for c in element.character_set.resolve(self.alphabet)}
                copied = element.group in copied_groups
                source = after[index]
                target = before[index + 1]
                if element.quantifier == "1":
                    for label in labels:
                        _add_arc(fst, source, label, label if copied else EPSILON, target)
                elif element.quantifier == "?":
                    for label in labels:
                        _add_arc(fst, source, label, label if copied else EPSILON, target)
                    preferred = pynini.concat(symbol_set_acceptor(labels),
                                              self._suffix_language(alternative, index + 1))
                    marker = self._new_marker(preferred.optimize())
                    _add_arc(fst, source, marker, EPSILON, target)
                else:  # "+"
                    loop = fst.add_state()
                    for label in labels:
                        _add_arc(fst, source, label, label if copied else EPSILON, loop)
                        _add_arc(fst, loop, label, label if copied else EPSILON, loop)
                    one = symbol_set_acceptor(labels)
                    preferred = pynini.concat(pynini.concat(one, pynini.closure(one.copy())),
                                              self._suffix_language(alternative, index + 1))
                    marker = self._new_marker(preferred.optimize())
                    _add_arc(fst, loop, marker, EPSILON, target)
        return fst

    def _build_transducer(self) -> pynini.Fst:
        pattern = self.pattern
        extended = self.sigma | set(self.markers)
        anything_extended = symbol_set_star(extended)
        only_markers = symbol_set_star(self.markers)

        matches = pynini.union(*[self._suffix_language(alternative, 0)
                                 for alternative in pattern.alternatives]).optimize()
        tail = only_markers if pattern.anchored_at_end else anything_extended

        # Each constraint is subtracted on its own: determinizing the union
        # of all forbidden languages at once blows up.
        constraints = [(COPY_MARKER, matches, epsilon_acceptor()
                        if pattern.anchored_at_start else anything_extended)]
        constraints += [(marker, preferred, anything_extended)
                        for marker, preferred in self.alternative_constraints]
        legal = anything_extended
        for marker, language, head in constraints:
            # Copying a character where a match starts is not allowed
            # (leftmost); taking a less preferred branch where the preferred
            # one succeeds is not allowed (backtracking priority of ? and +).
            illegal = pynini.concat(
                pynini.concat(pynini.concat(head, symbol_set_acceptor({marker})),
                              ignore_markers(language, self.markers)),
                tail).optimize()
            legal = pynini.difference(legal, illegal).optimize()

        insert_markers = pynini.Fst()
        state = insert_markers.add_state()
        insert_markers.set_start(state)
        insert_markers.set_final(state)
        for label in self.sigma:
            _add_arc(insert_markers, state, label, label, state)
        for marker in self.markers:
            _add_arc(insert_markers, state, EPSILON, marker, state)

        parser = pynini.compose(legal, self.parser)
        return pynini.compose(insert_markers, parser).optimize()


# --------------------------------------------------------------------------
# The symbolic string and the "re" replacement
# --------------------------------------------------------------------------

class PrintingLog(list):
    def append(self, line):
        import sys
        print(line, file=sys.stderr, flush=True)
        super().append(line)


class Builder:
    """Shared state of one symbolic run of ipa_uk.ipa."""

    def __init__(self, input_alphabet: Set[str], alphabet: Set[str], loop_domain: pynini.Fst,
                 collect_only: bool = False, maximal_loop_iterations: int = 20):
        self.input_alphabet = input_alphabet
        self.alphabet = alphabet
        self.loop_domain = loop_domain
        self.loop_start = None
        self.rule_cache = {}
        self.collect_only = collect_only
        self.maximal_loop_iterations = maximal_loop_iterations
        self.patterns_seen: List[str] = []
        self.literals_seen: Set[str] = set()
        self.log = PrintingLog()
        self.loop_iterations = 0

    def rule(self, pattern_text, replacement_text, is_template, description):
        key = (pattern_text, replacement_text, is_template)
        if key in self.rule_cache:
            return self.rule_cache[key]
        pattern = parse_pattern(pattern_text)
        replacement = parse_replacement(replacement_text, is_template)
        self.literals_seen |= pattern.literal_characters
        for kind, value in replacement:
            if kind == "literal":
                self.literals_seen |= set(value)
        if self.collect_only:
            return None
        rule = RewriteRule(pattern, replacement, self.alphabet, description)
        self.rule_cache[key] = rule
        return rule


class SymbolicText:
    """The value of a str variable inside ipa_uk.ipa: the list of rewrite
    rules applied so far (each one a transducer)."""

    def __init__(self, builder: Builder, rules: Tuple = ()):
        self.builder = builder
        self.rules = rules

    def _apply(self, rule: Optional[RewriteRule]) -> "SymbolicText":
        if rule is not None:
            self.builder.log.append(f"{len(self.rules) + 1:3} {rule.description}")
        return SymbolicText(self.builder, self.rules + (rule,))

    def lower(self) -> "SymbolicText":
        return self  # the Ada side lowers the word before the automaton

    def replace(self, old: str, new: str) -> "SymbolicText":
        rule = self.builder.rule(python_regular_expressions.escape(old), new, False,
                                 f"replace({old!r}, {new!r})")
        return self._apply(rule)

    def __eq__(self, other) -> bool:
        """Used only by the "while True" loop: prev_phonetic == phonetic.

        True when no rule of the loop body can match anything that the loop
        produced so far, starting from any string whose runs of consonant
        symbols are bounded (Builder.loop_domain): then one more iteration
        is the identity."""
        if not isinstance(other, SymbolicText):
            return NotImplemented
        if self.builder.collect_only:
            return True
        earlier, later = (self, other) if len(self.rules) <= len(other.rules) else (other, self)
        body = later.rules[len(earlier.rules):]
        builder = self.builder
        if builder.loop_start is None:
            builder.loop_start = len(earlier.rules)
        produced = builder.loop_domain
        for rule in later.rules[builder.loop_start:]:
            if rule is not None:
                produced = pynini.compose(produced, rule.transducer).optimize()
        for rule in body:
            if rule is None:
                continue
            common = pynini.compose(produced, rule.match_language())
            common.connect()
            if common.num_states() > 0:
                builder.loop_iterations += 1
                if builder.loop_iterations > builder.maximal_loop_iterations:
                    raise RuntimeError("loop does not reach a fixed point")
                builder.log.append(f"    loop iteration {builder.loop_iterations + 1}")
                return False
        builder.log.append(f"    loop finished after {builder.loop_iterations + 1} iterations")
        builder.loop_start = None
        return True

    def __hash__(self):
        return id(self)


class SymbolicRegularExpressionModule:
    """Stands in for the "re" module inside ipa_uk."""

    def __init__(self, builder: Builder):
        self.builder = builder

    def sub(self, pattern, replacement, text, count=0, flags=0):
        if not isinstance(text, SymbolicText):
            return python_regular_expressions.sub(pattern, replacement, text, count, flags)
        if count or flags or callable(replacement):
            raise NotImplementedError("re.sub with count/flags/callable")
        rule = self.builder.rule(pattern, replacement, True,
                                 f"re.sub({pattern!r}, {replacement!r})")
        return text._apply(rule)

    def findall(self, pattern, text, flags=0):
        if not isinstance(text, SymbolicText):
            return python_regular_expressions.findall(pattern, text, flags)
        return []  # only used for check_accent, which is off

    def __getattr__(self, name):
        return getattr(python_regular_expressions, name)
