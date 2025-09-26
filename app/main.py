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
    return False


def parse_subpattern(pattern, start, expect_close=False):
    alts = [[]]
    current_alt = alts[0]
    i = start
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            nxt = pattern[i + 1]
            if nxt == "1":
                current_alt.append(("BACKREF", 1))
                i += 2
                continue
            elif nxt == "d":
                current_alt.append(("DIGIT", None))
                i += 2
                continue
            elif nxt == "w":
                current_alt.append(("WORD", None))
                i += 2
                continue
            else:
                current_alt.append(("LITERAL", nxt))
                i += 2
                continue
        elif c == ".":
            current_alt.append(("DOT", None))
            i += 1
            continue
        elif c == "[":
            j = i + 1
            neg = False
            if j < n and pattern[j] == "^":
                neg = True
                j += 1
            chars = []
            k = j
            while k < n and pattern[k] != "]":
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
            if not current_alt:
                raise ValueError("Empty alternative")
            alts.append([])
            current_alt = alts[-1]
            i += 1
            continue
        elif c == "(":
            sub_alts, new_i = parse_subpattern(pattern, i + 1, expect_close=True)
            sub_tokens = sub_alts[0] if len(sub_alts) == 1 else [("OR", sub_alts)]
            current_alt.append(("CAPTURE", sub_tokens))
            i = new_i
            continue
        elif c == ")":
            if not expect_close:
                current_alt.append(("LITERAL", ")"))
                i += 1
                continue
            if not current_alt:
                raise ValueError("Empty alternative at end")
            return alts, i + 1
        else:
            current_alt.append(("LITERAL", c))
            i += 1
    if expect_close:
        raise ValueError("Unclosed group")
    if not current_alt:
        raise ValueError("Empty pattern")
    return alts, i


def tokenize(pattern):
    alts, _ = parse_subpattern(pattern, 0, expect_close=False)
    if len(alts) > 1:
        return [("OR", alts)]
    else:
        return alts[0]


def match_here(tokens, s, idx, cs=-1, ce=-1):
    n = len(s)
    if not tokens:
        return idx, cs, ce

    ttype, val = tokens[0]

    if ttype == "START":
        if idx != 0:
            return None
        return match_here(tokens[1:], s, idx, cs, ce)

    if ttype == "END":
        if idx != n:
            return None
        return match_here(tokens[1:], s, idx, cs, ce)

    if ttype == "CAPTURE":
        sub_tokens = val
        sub_pos, sub_cs, sub_ce = match_here(sub_tokens, s, idx, -1, -1)
        if sub_pos is None:
            return None
        group_cs = idx
        group_ce = sub_pos
        rest_pos, r_cs, r_ce = match_here(tokens[1:], s, sub_pos, group_cs, group_ce)
        if rest_pos is not None:
            return rest_pos, group_cs, group_ce
        return None

    if ttype == "BACKREF":
        if cs == -1 or ce == -1:
            return None
        captured = s[cs:ce]
        cl = len(captured)
        if idx + cl > n or s[idx:idx + cl] != captured:
            return None
        rest_pos, new_cs, new_ce = match_here(tokens[1:], s, idx + cl, cs, ce)
        if rest_pos is not None:
            return rest_pos, new_cs, new_ce
        return None

    if ttype == "PLUS":
        inner = val
        if idx >= n or not match_token(inner, s[idx]):
            return None
        j = idx + 1
        while j < n and match_token(inner, s[j]):
            j += 1
        for k in range(j, idx, -1):
            rest_pos, new_cs, new_ce = match_here(tokens[1:], s, k, cs, ce)
            if rest_pos is not None:
                return rest_pos, new_cs, new_ce
        return None

    if ttype == "QUESTION":
        inner = val
        if idx < n and match_token(inner, s[idx]):
            rest_pos, new_cs, new_ce = match_here(tokens[1:], s, idx + 1, cs, ce)
            if rest_pos is not None:
                return rest_pos, new_cs, new_ce
        rest_pos, new_cs, new_ce = match_here(tokens[1:], s, idx, cs, ce)
        if rest_pos is not None:
            return rest_pos, new_cs, new_ce
        return None

    if ttype == "OR":
        for alt in val:
            alt_pos, new_cs, new_ce = match_here(alt, s, idx, cs, ce)
            if alt_pos is not None:
                rest_pos, r_cs, r_ce = match_here(tokens[1:], s, alt_pos, new_cs, new_ce)
                if rest_pos is not None:
                    return rest_pos, r_cs, r_ce
        return None

    # Normal token match
    if idx >= n or not match_token((ttype, val), s[idx]):
        return None
    return match_here(tokens[1:], s, idx + 1, cs, ce)


def match(tokens, s):
    n = len(s)
    if tokens and tokens[0][0] == "START":
        res = match_here(tokens, s, 0, -1, -1)
        return res is not None
    for i in range(n + 1):
        res = match_here(tokens, s, i, -1, -1)
        if res is not None:
            return True
    return False


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
