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


def match_or(alt_lists, s, idx, captures, open_groups):
    """Match any alternative in an OR."""
    for alt in alt_lists:
        res = match_here(alt, s, idx, captures, open_groups)
        if res is not None:
            return res
    return None


def match_sub(sub, s, idx, captures, open_groups):
    """Match a subpattern which is either a list (sequence) or OR."""
    n = len(s)
    if isinstance(sub, list):
        return match_here(sub, s, idx, captures, open_groups)
    elif sub[0] == "OR":
        return match_or(sub[1], s, idx, captures, open_groups)
    return None


def match_atom(token, s, idx, captures, open_groups):
    """Match a single atom/token tree."""
    n = len(s)
    ttype, val = token
    if ttype == "START":
        if idx != 0:
            return None
        return idx, captures
    if ttype == "END":
        if idx != n:
            return None
        return idx, captures
    if ttype in ["LITERAL", "DOT", "DIGIT", "WORD", "CLASS", "NEG_CLASS"]:
        if idx >= n or not match_token(token, s[idx]):
            return None
        return idx + 1, captures
    if ttype == "BACKREF":
        group_num = val
        if group_num in captures:
            cap_start, cap_end = captures[group_num]
            clen = cap_end - cap_start
            if idx + clen > n or s[idx:idx + clen] != s[cap_start:cap_end]:
                return None
            return idx + clen, captures
        elif group_num in open_groups:
            cap_start = open_groups[group_num]
            plen = idx - cap_start
            if idx + plen > n or s[idx:idx + plen] != s[cap_start:idx]:
                return None
            return idx + plen, captures
        else:
            return None
    if ttype == "CAPTURE":
        group_id, sub_tokens = val
        new_open = open_groups.copy()
        new_open[group_id] = idx
        sub_res = match_sub(sub_tokens, s, idx, captures, new_open)
        if sub_res is None:
            return None
        sub_pos, sub_captures = sub_res
        new_captures = sub_captures.copy()
        new_captures[group_id] = (idx, sub_pos)
        del new_open[group_id]
        return sub_pos, new_captures
    if ttype == "OR":
        return match_or(val, s, idx, captures, open_groups)
    if ttype == "PLUS":
        inner_token = val
        res = match_atom(inner_token, s, idx, captures, open_groups)
        if res is None:
            return None
        pos, cap = res
        while True:
            next_res = match_atom(inner_token, s, pos, cap, open_groups)
            if next_res is None:
                break
            pos, cap = next_res
        return pos, cap
    if ttype == "QUESTION":
        inner_token = val
        res = match_atom(inner_token, s, idx, captures, open_groups)
        if res is not None:
            return res
        return idx, captures
    return None


def match_here(tokens, s, idx, captures, open_groups):
    n = len(s)
    if not tokens:
        return idx, captures

    ttype, val = tokens[0]

    if ttype == "START":
        if idx != 0:
            return None
        return match_here(tokens[1:], s, idx, captures, open_groups)

    if ttype == "END":
        if idx != n:
            return None
        return match_here(tokens[1:], s, idx, captures, open_groups)

    if ttype == "CAPTURE":
        group_id, sub_tokens = val
        new_open = open_groups.copy()
        new_open[group_id] = idx
        sub_res = match_sub(sub_tokens, s, idx, captures, new_open)
        if sub_res is None:
            return None
        sub_pos, sub_captures = sub_res
        new_captures = sub_captures.copy()
        new_captures[group_id] = (idx, sub_pos)
        del new_open[group_id]
        rest_res = match_here(tokens[1:], s, sub_pos, new_captures, new_open)
        return rest_res

    if ttype == "OR":
        or_res = match_or(val, s, idx, captures, open_groups)
        if or_res is None:
            return None
        or_pos, or_captures = or_res
        return match_here(tokens[1:], s, or_pos, or_captures, open_groups)

    if ttype == "BACKREF":
        group_num = val
        if group_num in captures:
            cap_start, cap_end = captures[group_num]
            clen = cap_end - cap_start
            if idx + clen > n or s[idx:idx + clen] != s[cap_start:cap_end]:
                return None
            return match_here(tokens[1:], s, idx + clen, captures, open_groups)
        elif group_num in open_groups:
            cap_start = open_groups[group_num]
            plen = idx - cap_start
            if idx + plen > n or s[idx:idx + plen] != s[cap_start:idx]:
                return None
            return match_here(tokens[1:], s, idx + plen, captures, open_groups)
        else:
            return None

    if ttype == "PLUS":
        inner_token = val
        res = match_atom(inner_token, s, idx, captures, open_groups)
        if res is None:
            return None
        pos, cap = res
        possible = [(pos, cap)]
        while True:
            next_res = match_atom(inner_token, s, pos, cap, open_groups)
            if next_res is None:
                break
            pos, cap = next_res
            possible.append((pos, cap))
        for p_pos, p_cap in reversed(possible):
            rest_res = match_here(tokens[1:], s, p_pos, p_cap, open_groups)
            if rest_res is not None:
                return rest_res
        return None

    if ttype == "QUESTION":
        inner_token = val
        res = match_atom(inner_token, s, idx, captures, open_groups)
        if res is not None:
            q_pos, q_cap = res
            rest_res = match_here(tokens[1:], s, q_pos, q_cap, open_groups)
            if rest_res is not None:
                return rest_res
        return match_here(tokens[1:], s, idx, captures, open_groups)

    # Simple token match
    if idx >= n or not match_token((ttype, val), s[idx]):
        return None
    return match_here(tokens[1:], s, idx + 1, captures, open_groups)


def match(tokens, s):
    n = len(s)
    for i in range(n + 1):
        res = match_here(tokens, s, i, {}, {})
        if res is not None:
            return True
    return False


def parse_subpattern(pattern, start, expect_close=False, next_group=[1]):
    alts = [[]]
    current_alt = alts[0]
    i = start
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            j = i + 1
            if pattern[j] == "d":
                current_alt.append(("DIGIT", None))
                i = j + 1
                continue
            elif pattern[j] == "w":
                current_alt.append(("WORD", None))
                i = j + 1
                continue
            elif pattern[j].isdigit():
                k = j + 1
                while k < n and pattern[k].isdigit():
                    k += 1
                group_num = int(pattern[j:k])
                current_alt.append(("BACKREF", group_num))
                i = k
                continue
            else:
                escaped = pattern[j]
                current_alt.append(("LITERAL", escaped))
                i = j + 1
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
