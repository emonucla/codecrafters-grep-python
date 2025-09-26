import sys
from abc import ABC, abstractmethod
from typing import Set, List, Optional, Dict
from dataclasses import dataclass, field

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
            return {MatchState(state.pos + 1, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return f"Literal({self.char})"


class DigitMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line) and line[state.pos].isdigit():
            return {MatchState(state.pos + 1, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return "DigitMatcher()"


class WordMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line) and (line[state.pos].isalnum() or line[state.pos] == '_'):
            return {MatchState(state.pos + 1, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return "WordMatcher()"


class SequenceMatcher(Matcher):
    def __init__(self, matchers: List[Matcher]):
        self.matchers = matchers

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        states = {state}
        for matcher in self.matchers:
            next_states = set()
            for st in states:
                next_states |= matcher.match(line, st)
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
    def __init__(self, left: Matcher, right: Matcher):
        self.left = left
        self.right = right

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        return self.left.match(line, state) | self.right.match(line, state)

    def __str__(self) -> str:
        return f"AlternationMatcher({self.left}, {self.right})"


class OptionalMatcher(Matcher):
    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        return self.matcher.match(line, state) | {MatchState(state.pos, dict(state.groups))}

    def __str__(self) -> str:
        return f"OptionalMatcher({self.matcher})"


class PlusMatcher(Matcher):
    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        states = self.matcher.match(line, state)
        if not states:
            return set()
        last_iter_states = states
        while last_iter_states:
            next_states = set()
            for st in last_iter_states:
                next_states |= self.matcher.match(line, st)
            if not next_states:
                break
            states |= next_states
            last_iter_states = next_states
        return states

    def __str__(self) -> str:
        return f"PlusMatcher({self.matcher})"


class StarMatcher(Matcher):
    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        states = {state}  # zero or more
        current_states = {state}
        while current_states:
            next_states = set()
            for st in current_states:
                next_states |= self.matcher.match(line, st)
            states |= next_states
            current_states = next_states
        return states

    def __str__(self) -> str:
        return f"StarMatcher({self.matcher})"


class AnchorStartMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos == 0:
            return {MatchState(0, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return "AnchorStartMatcher()"


class AnchorEndMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos == len(line):
            return {MatchState(state.pos, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return "AnchorEndMatcher()"


class AnyMatcher(Matcher):
    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos < len(line):
            return {MatchState(state.pos + 1, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return "AnyMatcher()"


class CharClassMatcher(Matcher):
    def __init__(self, charset: set, is_negated: bool):
        self.charset = charset
        self.is_negated = is_negated

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if state.pos >= len(line):
            return set()
        ch = line[state.pos]
        matches = (ch not in self.charset) if self.is_negated else (ch in self.charset)
        if matches:
            return {MatchState(state.pos + 1, dict(state.groups))}
        return set()

    def __str__(self) -> str:
        return f"CharClassMatcher({self.charset}, {self.is_negated})"


class CaptureGroupMatcher(Matcher):
    def __init__(self, matcher: Matcher, group_id: int):
        self.matcher = matcher
        self.group_id = group_id

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        next_states = self.matcher.match(line, state)
        result = set()
        for next_state in next_states:
            new_groups = dict(next_state.groups)
            captured = line[state.pos : next_state.pos]
            new_groups[self.group_id] = captured
            result.add(MatchState(next_state.pos, new_groups))
        return result

    def __str__(self) -> str:
        return f"CaptureGroupMatcher({self.matcher}, {self.group_id})"


class BackreferenceMatcher(Matcher):
    def __init__(self, group_id: int):
        self.group_id = group_id

    def match(self, line: str, state: MatchState) -> Set[MatchState]:
        if self.group_id in state.groups:
            group_match = state.groups[self.group_id]
            match_len = len(group_match)
            if state.pos + match_len <= len(line) and line[state.pos : state.pos + match_len] == group_match:
                return {MatchState(state.pos + match_len, dict(state.groups))}
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
        if self.i < len(self.pattern):
            c = self.pattern[self.i]
            self.i += 1
            return c
        return None

    def parse(self) -> Matcher:
        res = self.parse_expression()
        if self.peek() is not None:
            raise ValueError("Unexpected characters at end of pattern")
        return res

    def parse_expression(self) -> Matcher:
        left = self.parse_term()
        while self.peek() == "|":
            self.advance()
            right = self.parse_term()
            left = AlternationMatcher(left, right)
        return left

    def parse_term(self) -> Matcher:
        parts = []
        while (c := self.peek()) is not None and c not in ["|", ")"]:
            parts.append(self.parse_factor())
        if len(parts) == 0:
            raise ValueError("Empty term in pattern")
        if len(parts) == 1:
            return parts[0]
        return SequenceMatcher(parts)

    def parse_factor(self) -> Matcher:
        atom = self.parse_atom()
        quantifier = self.peek()
        if quantifier in ["?", "+", "*"]:
            self.advance()
            if quantifier == "?":
                return OptionalMatcher(atom)
            elif quantifier == "+":
                return PlusMatcher(atom)
            elif quantifier == "*":
                return StarMatcher(atom)
        return atom

    def parse_atom(self) -> Matcher:
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
            self.advance()  # consume \
            if self.peek() is None:
                raise ValueError("Incomplete escape sequence")
            next_c = self.advance()  # consume the escape character
            if next_c == "d":
                return DigitMatcher()
            elif next_c == "w":
                return WordMatcher()
            elif next_c.isdigit():
                # Collect additional digits for backreference
                digits = next_c
                while self.peek() is not None and self.peek().isdigit():
                    digits += self.advance()
                group_id = int(digits)
                return BackreferenceMatcher(group_id)
            else:
                # Literal escape
                return LiteralMatcher(next_c)
        if c == "[":
            return self.parse_charset()
        if c == "(":
            self.advance()
            group_id = self.next_group_id
            self.next_group_id += 1
            expr = self.parse_expression()
            if self.advance() != ")":
                raise ValueError("Expected closing parenthesis ')'")
            return CaptureGroupMatcher(expr, group_id)
        # Literal character
        return LiteralMatcher(self.advance())

    def parse_charset(self) -> Matcher:
        self.advance()  # Consume [
        is_negated = False
        if self.peek() == "^":
            is_negated = True
            self.advance()
        charset = set()
        while self.peek() is not None and self.peek() != "]":
            c = self.advance()
            if c == "\\" and self.peek() is not None:
                # Escaped character in class
                c = self.advance()
            charset.add(c)
        if self.advance() != "]":
            raise ValueError("Expected closing bracket ']'")
        return CharClassMatcher(charset, is_negated)


def match_pattern(input_line: str, pattern: str) -> bool:
    try:
        parser = PatternParser(pattern)
        matcher = parser.parse()
        n = len(input_line)
        for start_pos in range(n + 1):
            initial_state = MatchState(start_pos, {})
            states = matcher.match(input_line, initial_state)
            if states:
                return True
        return False
    except ValueError as e:
        print(f"Pattern parsing error: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) != 4 or sys.argv[1] != "-E":
        print("Usage: ./your_program.py -E <pattern> <filename>", file=sys.stderr)
        sys.exit(1)

    pattern = sys.argv[2]
    filename = sys.argv[3]

    try:
        with open(filename, 'r') as f:
            input_line = f.read().rstrip('\n')
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if match_pattern(input_line, pattern):
        print(input_line)
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
