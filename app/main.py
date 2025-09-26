import sys
from abc import ABC, abstractmethod
from typing import Set, List, Type, Optional, Dict
from dataclasses import dataclass, field
from copy import deepcopy

# import pyparsing - available if you need it!
# import lark - available if you need it!


@dataclass
class MatchState:
    pos: int
    groups: Dict[int, str] = field(compare=False)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, MatchState)
            and self.pos == other.pos
            and self.groups == other.groups
        )

    def __hash__(self) -> int:
        return hash((self.pos, tuple(sorted(self.groups.items()))))


class Matcher(ABC):
    @abstractmethod
    def match(self, line: str, state: MatchState) -> Set[MatchState]: ...


class LiteralMatcher(Matcher):
    def __init__(self, char: str):
        self.char = char

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line) and line[state.pos] == self.char:
            return {MatchState(state.pos + 1, state.groups)}
        return set()

    def __str__(self) -> str:
        return f"Literal({self.char})"


class DigitMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line) and line[state.pos].isdigit():
            return {MatchState(state.pos + 1, state.groups)}
        return set()

    def __str__(self) -> str:
        return "DigitMatcher()"


class AlphanumericMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line) and line[state.pos].isalnum():
            return {MatchState(state.pos + 1, state.groups)}
        return set()

    def __str__(self) -> str:
        return "AlphanumericMatcher()"


class SequenceMatcher(Matcher):
    def __init__(self, matchers: List[Matcher]):
        self.matchers = matchers

    def add_matcher(self, matcher: Matcher):
        self.matchers.append(matcher)

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        states = {state}
        for matcher in self.matchers:
            next_states = set()
            for state in states:
                next_states |= matcher.match(line, state)
            states = next_states
            if not states:
                break
        return states

    def __str__(self) -> str:
        return (
            "SequenceMatcher("
            + ", ".join(str(matcher) for matcher in self.matchers)
            + ")"
        )


class AlternationMatcher(Matcher):
    def __init__(self, left: Type[Matcher], right: Type[Matcher]):
        self.left = left
        self.right = right

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        return self.left.match(line, state) | self.right.match(line, state)

    def __str__(self) -> str:
        return f"AlternationMatcher({self.left}, {self.right})"


class OptionalMatcher(Matcher):
    def __init__(self, matcher: Type[Matcher]):
        self.matcher = matcher

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        return self.matcher.match(line, state) | {state}

    def __str__(self) -> str:
        return f"OptionalMatcher({self.matcher})"


class PlusMatcher(Matcher):
    def __init__(self, matcher: Type[Matcher]):
        self.matcher = matcher

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        states = self.matcher.match(line, state)
        last_iter_states = states
        while last_iter_states:
            next_states = set()
            for state in last_iter_states:
                next_states |= self.matcher.match(line, state)
            states |= next_states
            last_iter_states = next_states
        return states

    def __str__(self) -> str:
        return f"PlusMatcher({self.matcher})"


class AnchorStartMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos == 0:
            return {MatchState(0, state.groups)}
        return set()

    def __str__(self) -> str:
        return "AnchorStartMatcher()"


class AnchorEndMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos == len(line):
            return {MatchState(state.pos, state.groups)}
        return set()

    def __str__(self) -> str:
        return "AnchorEndMatcher()"


class AnyMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line):
            return {MatchState(state.pos + 1, state.groups)}
        return set()

    def __str__(self) -> str:
        return "AnyMatcher()"


class CharClassMatcher(Matcher):
    def __init__(self, charset: List[str], is_negated: bool):
        self.charset = charset
        self.is_negated = is_negated

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos >= len(line):
            return set()
        if self.is_negated and line[state.pos] not in self.charset:
            return {MatchState(state.pos + 1, state.groups)}
        if not self.is_negated and line[state.pos] in self.charset:
            return {MatchState(state.pos + 1, state.groups)}
        return set()

    def __str__(self) -> str:
        return f"CharClassMatcher({self.charset}, {self.is_negated})"


class CaptureGroupMatcher(Matcher):
    def __init__(self, matcher: Type[Matcher], group_id: int):
        self.matcher = matcher
        self.group_id = group_id

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        next_states = self.matcher.match(line, state)
        for next_state in next_states:
            next_state.groups = deepcopy(next_state.groups)
            next_state.groups[self.group_id] = line[state.pos : next_state.pos]
        return next_states

    def __str__(self) -> str:
        return f"CaptureGroupMatcher({self.matcher}, {self.group_id})"

class BackreferenceMatcher(Matcher):
    def __init__(self, group_id: int):
        self.group_id = group_id

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if self.group_id in state.groups:
            group_match = state.groups[self.group_id]
            if line[state.pos : state.pos + len(group_match)] == group_match:
                return {MatchState(state.pos + len(group_match), state.groups)}
        return set()

    def __str__(self) -> str:
        return f"BackreferenceMatcher({self.group_id})"


class PatternParser:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.i: int = 0
        self.next_group_id: int = 1

    def peek(self) -> Optional[str]:
        if self.i < len(self.pattern):
            return self.pattern[self.i]
        return None

    def advance(self) -> Optional[str]:
        c = self.peek()
        if c is not None:
            self.i += 1
        return c

    def parse(self) -> Type[Matcher]:
        res = self.parse_expression()
        if self.peek() is not None:
            raise ValueError("Unexpected characters")
        return res

    def parse_expression(self) -> Type[Matcher]:
        left = self.parse_term()
        while self.peek() == "|":
            self.advance()
            right = self.parse_term()
            left = AlternationMatcher(left, right)
        return left

    def parse_term(self) -> Type[Matcher]:
        parts = []
        while (c := self.peek()) is not None and c not in ["|", ")"]:
            parts.append(self.parse_factor())
        if len(parts) == 1:
            return parts[0]
        return SequenceMatcher(parts)

    def parse_factor(self) -> Type[Matcher]:
        atom = self.parse_atom()
        if (quantifier := self.peek()) in ["?", "+"]:
            self.advance()
            if quantifier == "?":
                return OptionalMatcher(atom)
            if quantifier == "+":
                return PlusMatcher(atom)
        return atom

    def parse_atom(self) -> Type[Matcher]:
        c = self.peek()
        if c is None:
            raise ValueError("Unexpected end of pattern")

        if c == "^":
            self.advance()
            return AnchorStartMatcher()

        if c == "$":
            self.advance()
            return AnchorEndMatcher()

        if c == ".":
            self.advance()
            return AnyMatcher()

        if c == "\\":
            self.advance()
            c = self.advance()
            if c.isdigit():
                return BackreferenceMatcher(int(c))
            if c == "d":
                return DigitMatcher()
            if c == "w":
                return AlphanumericMatcher()
            if c == "\\":
                return LiteralMatcher("\\")
            return LiteralMatcher(c)

        if c == "[":
            return self.parse_charset()

        if c == "(":
            self.advance()
            group_id = self.next_group_id
            self.next_group_id += 1

            expr = self.parse_expression()
            if self.advance() != ")":
                raise ValueError("Expected ')'")

            return CaptureGroupMatcher(expr, group_id)

        return LiteralMatcher(self.advance())

    def parse_charset(self) -> Type[Matcher]:
        assert self.advance() == "["
        is_negated = False
        if self.peek() == "^":
            is_negated = True
            self.advance()
        charset = []
        while (c := self.peek()) is not None and c != "]":
            charset.append(self.advance())
        if self.advance() != "]":
            raise ValueError("Expected ']'")
        return CharClassMatcher(charset, is_negated)


def match_pattern(input_line, pattern):
    parser = PatternParser(pattern)
    matcher = parser.parse()

    for pos in range(len(input_line)):
        end_pos = matcher.match(input_line, MatchState(pos, {}))
        if end_pos:
            return True
    return False


def main():
    pattern = sys.argv[2]
    input_line = sys.stdin.read()

    if sys.argv[1] != "-E":
        print("Expected first argument to be '-E'")
        exit(1)

    if match_pattern(input_line, pattern):
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()