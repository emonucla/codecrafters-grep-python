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


def parse_subpattern(pattern, start, expect_close=False, next_group=[1]):
    alts = [[]]
    current_alt = alts[0]
    i = start
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            nxt = pattern[i + 1]
            if nxt.isdigit():
                group_num = int(nxt)
                current_alt.append(("BACKREF", group_num))
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
            group_id = next_group[0]
            next_group[0] += 1
            sub_alts, new_i, next_group = parse_subpattern(pattern, i + 1, expect_close=True, next_group=next_group)
            sub_tokens = sub_alts[0] if len(sub_alts) == 1 else [("OR", sub_alts)]
            current_alt.append(("CAPTURE", (group_id, sub_tokens)))
            i = new_i
            continue
        elif c == ")":
            if not expect_close:
                current_alt.append(("LITERAL", ")"))
                i += 1
                continue
            if not current_alt:
                raise ValueError("Empty alternative at end")
            return alts, i + 1, next_group
        else:
            current_alt.append(("LITERAL", c))
            i += 1
    if expect_close:
        raise ValueError("Unclosed group")
    if not current_alt:
        raise ValueError("Empty pattern")
    return alts, i, next_group


def tokenize(pattern):
    next_group = [1]
    alts, _, _ = parse_subpattern(pattern, 0, expect_close=False, next_group=next_group)
    if len(alts) > 1:
        return [("OR", alts)]
    else:
        return alts[0]


def match_here(tokens, s, idx, captures):
    n = len(s)
    if not tokens:
        return idx, captures

    ttype, val = tokens[0]

    if ttype == "START":
        if idx != 0:
            return None
        return match_here(tokens[1:], s, idx, captures)

    if ttype == "END":
        if idx != n:
            return None
        return match_here(tokens[1:], s, idx, captures)

    if ttype == "CAPTURE":
        group_id, sub_tokens = val
        sub_res = match_here(sub_tokens, s, idx, captures)
        if sub_res is None:
            return None
        sub_pos, sub_captures = sub_res
        new_captures = sub_captures.copy()
        new_captures[group_id] = (idx, sub_pos)
        rest_res = match_here(tokens[1:], s, sub_pos, new_captures)
        if rest_res is not None:
            return rest_res
        return None

    if ttype == "BACKREF":
        group_num = val
        if group_num not in captures:
            return None
        cap_start, cap_end = captures[group_num]
        captured_str = s[cap_start:cap_end]
        clen = len(captured_str)
        if idx + clen > n or s[idx:idx + clen] != captured_str:
            return None
        return match_here(tokens[1:], s, idx + clen, captures)

    if ttype == "PLUS":
        inner = val
        if idx >= n or not match_token(inner, s[idx]):
            return None
        j = idx + 1
        while j < n and match_token(inner, s[j]):
            j += 1
        for k in range(j, idx, -1):
            rest_res = match_here(tokens[1:], s, k, captures)
            if rest_res is not None:
                return rest_res
        return None

    if ttype == "QUESTION":
        inner = val
        # Try one first (greedy)
        res = None
        if idx < n and match_token(inner, s[idx]):
            res = match_here(tokens[1:], s, idx + 1, captures)
            if res is not None:
                return res
        # Try zero
        res = match_here(tokens[1:], s, idx, captures)
        return res

    if ttype == "OR":
        for alt in val:
            alt_res = match_here(alt, s, idx, captures)
            if alt_res is not None:
                alt_pos, alt_captures = alt_res
                rest_res = match_here(tokens[1:], s, alt_pos, alt_captures)
                if rest_res is not None:
                    return rest_res
        return None

    # Normal token match
    if idx >= n or not match_token((ttype, val), s[idx]):
        return None
    return match_here(tokens[1:], s, idx + 1, captures)


def match(tokens, s):
    n = len(s)
    for i in range(n + 1):
        res = match_here(tokens, s, i, {})
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
