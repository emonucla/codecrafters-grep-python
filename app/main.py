#!/usr/bin/env python3
import sys

def match_token(token, ch):
    """Match a single character against a token."""
    ttype, val = token
    if ttype == "LITERAL":
        return ch == val
    elif ttype == "DOT":
        return True
    elif ttype == "DIGIT":
        return ch.isdigit()
    elif ttype == "WORD":
        return ch.isalnum() or ch == "_"
    elif ttype == "CLASS":
        return ch in val
    elif ttype == "NEG_CLASS":
        return ch not in val
    # For tokens that are themselves token-tuples (like PLUS/QUESTION storing inner token),
    # match_token expects a token tuple; if given here, it's an error — handled at callsite.
    return False


def parse_subpattern(pattern, start, expect_close=False, next_group=[1]):
    """
    Parse pattern from `start` returning (alts, new_index, next_group_ref).
    alts is a list of alternatives; each alternative is a list of tokens.
    Tokens are tuples like ("LITERAL", "a"), ("CAPTURE", (id, sub_tokens)), ("BACKREF", n), etc.
    """
    alts = [[]]
    current_alt = alts[0]
    i = start
    n = len(pattern)
    while i < n:
        c = pattern[i]

        if c == "\\" and i + 1 < n:
            # handle escapes and multi-digit backrefs
            nxt = pattern[i + 1]
            if nxt.isdigit():
                j = i + 1
                digits = []
                while j < n and pattern[j].isdigit():
                    digits.append(pattern[j])
                    j += 1
                group_num = int("".join(digits))
                current_alt.append(("BACKREF", group_num))
                i = j
                continue
            elif nxt == "d":
                current_alt.append(("DIGIT", None))
                i += 2
                continue
            elif nxt == "w":
                current_alt.append(("WORD", None))
                i += 2
                continue
            elif nxt == "\\":
                current_alt.append(("LITERAL", "\\"))
                i += 2
                continue
            else:
                # Any other escaped char treated as literal (e.g. \. or \*)
                current_alt.append(("LITERAL", nxt))
                i += 2
                continue

        elif c == ".":
            current_alt.append(("DOT", None))
            i += 1
            continue

        elif c == "[":
            # character class
            j = i + 1
            if j >= n:
                raise ValueError("Unclosed character class")
            neg = False
            if pattern[j] == "^":
                neg = True
                j += 1
            chars = []
            k = j
            # Support ranges like a-z? (Not implemented here — keep simple per original)
            while k < n and pattern[k] != "]":
                # handle escaping inside class: \] or \- if present
                if pattern[k] == "\\" and k + 1 < n:
                    chars.append(pattern[k+1])
                    k += 2
                else:
                    chars.append(pattern[k])
                    k += 1
            if k == n:
                raise ValueError("Unclosed character class")
            val = "".join(chars)
            if neg:
                current_alt.append(("NEG_CLASS", val))
            else:
                current_alt.append(("CLASS", val))
            i = k + 1
            continue

        elif c == "^":
            current_alt.append(("START", None))
            i += 1
            continue

        elif c == "$":
            current_alt.append(("END", None))
            i += 1
            continue

        elif c == "+":
            if not current_alt:
                raise ValueError("Nothing to repeat for +")
            prev = current_alt.pop()
            current_alt.append(("PLUS", prev))
            i += 1
            continue

        elif c == "?":
            if not current_alt:
                raise ValueError("Nothing to repeat for ?")
            prev = current_alt.pop()
            current_alt.append(("QUESTION", prev))
            i += 1
            continue

        elif c == "|":
            # Start a new alternative
            alts.append([])
            current_alt = alts[-1]
            i += 1
            continue

        elif c == "(":
            group_id = next_group[0]
            next_group[0] += 1
            # parse subpattern for the group
            sub_alts, new_i, next_group = parse_subpattern(pattern, i + 1, expect_close=True, next_group=next_group)
            # If the group has multiple alternatives, represent them with an OR token inside the capture
            if len(sub_alts) == 1:
                sub_tokens = sub_alts[0]
            else:
                sub_tokens = [("OR", sub_alts)]
            current_alt.append(("CAPTURE", (group_id, sub_tokens)))
            i = new_i
            continue

        elif c == ")":
            if not expect_close:
                # unmatched ) treated as literal (to be permissive)
                current_alt.append(("LITERAL", ")"))
                i += 1
                continue
            # closing a group
            # ensure alternatives are not empty — allow empty alternative (which matches empty string)
            return alts, i + 1, next_group

        else:
            current_alt.append(("LITERAL", c))
            i += 1

    if expect_close:
        raise ValueError("Unclosed group")
    return alts, i, next_group


def tokenize(pattern):
    next_group = [1]
    alts, _, _ = parse_subpattern(pattern, 0, expect_close=False, next_group=next_group)
    if len(alts) > 1:
        return [("OR", alts)]
    else:
        return alts[0]


def match_here(tokens, s, idx, captures):
    """
    Attempt to match tokens starting at s[idx].
    `captures` is a dict mapping capture_id -> (start_idx, end_idx) relative to s.
    Returns either (new_index, new_captures) on success or None on failure.
    """
    n = len(s)
    if not tokens:
        return idx, captures

    ttype, val = tokens[0]

    # Anchors
    if ttype == "START":
        if idx != 0:
            return None
        return match_here(tokens[1:], s, idx, captures)

    if ttype == "END":
        if idx != n:
            return None
        return match_here(tokens[1:], s, idx, captures)

    # Capturing group
    if ttype == "CAPTURE":
        group_id, sub_tokens = val
        # match the sub_tokens starting at idx; sub_tokens may produce new captures (inner groups)
        sub_res = match_here(sub_tokens, s, idx, captures)
        if sub_res is None:
            return None
        sub_pos, sub_captures = sub_res
        # record this group's span
        new_captures = sub_captures.copy()
        new_captures[group_id] = (idx, sub_pos)
        # continue with rest using the updated captures
        rest_res = match_here(tokens[1:], s, sub_pos, new_captures)
        if rest_res is not None:
            return rest_res
        return None

    # Backreference
    if ttype == "BACKREF":
        group_num = val
        if group_num not in captures:
            return None
        cap_start, cap_end = captures[group_num]
        captured_str = s[cap_start:cap_end]
        clen = len(captured_str)
        if idx + clen > n or s[idx:idx + clen] != captured_str:
            return None
        rest_res = match_here(tokens[1:], s, idx + clen, captures)
        if rest_res is not None:
            return rest_res
        return None

    # PLUS quantifier (one or more) - greedy then backtrack
    if ttype == "PLUS":
        inner = val  # inner is a token tuple
        # first ensure at least one match
        if idx >= n or not (isinstance(inner, tuple) and match_token(inner, s[idx])):
            return None
        j = idx + 1
        # consume as many as possible
        while j < n and match_token(inner, s[j]):
            j += 1
        # backtrack: try from longest to shortest
        for k in range(j, idx, -1):
            rest_res = match_here(tokens[1:], s, k, captures)
            if rest_res is not None:
                return rest_res
        return None

    # QUESTION quantifier (zero or one) - greedy then try zero
    if ttype == "QUESTION":
        inner = val
        if idx < n and isinstance(inner, tuple) and match_token(inner, s[idx]):
            rest_res = match_here(tokens[1:], s, idx + 1, captures)
            if rest_res is not None:
                return rest_res
        rest_res = match_here(tokens[1:], s, idx, captures)
        if rest_res is not None:
            return rest_res
        return None

    # OR token (top-level or inside another construct)
    if ttype == "OR":
        for alt in val:  # val is list of alternative token-lists
            alt_res = match_here(alt, s, idx, captures)
            if alt_res is not None:
                alt_pos, alt_captures = alt_res
                rest_res = match_here(tokens[1:], s, alt_pos, alt_captures)
                if rest_res is not None:
                    return rest_res
        return None

    # Normal single-token match (LITERAL, DOT, DIGIT, WORD, CLASS, NEG_CLASS)
    if idx >= n or not match_token((ttype, val), s[idx]):
        return None
    return match_here(tokens[1:], s, idx + 1, captures)


def match(tokens, s):
    """
    For now behave like full-match: entire input must be matched (pos == len(s)).
    This mirrors the behavior in your original program.
    """
    res = match_here(tokens, s, 0, {})
    if res is None:
        return False
    pos, _ = res
    return pos == len(s)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "-E":
        print("Usage: ./your_program.py -E <pattern>")
        sys.exit(1)

    pattern = sys.argv[2]
    input_text = sys.stdin.read()

    tokens = tokenize(pattern)
    if match(tokens, input_text):
        sys.exit(0)
    else:
        sys.exit(1)
