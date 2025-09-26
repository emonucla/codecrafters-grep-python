import sys

def match_token(token, ch):
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
        if pattern[i:i+3] == "(?=":
            sub_alts, new_i, next_group = parse_subpattern(pattern, i + 3, expect_close=True, next_group=next_group)
            sub_tokens = sub_alts[0] if len(sub_alts) == 1 else [("OR", sub_alts)]
            current_alt.append(("LOOKAHEAD_POS", sub_tokens))
            i = new_i
            continue
        elif pattern[i:i+4] == "(?!":
            sub_alts, new_i, next_group = parse_subpattern(pattern, i + 4, expect_close=True, next_group=next_group)
            sub_tokens = sub_alts[0] if len(sub_alts) == 1 else [("OR", sub_alts)]
            current_alt.append(("LOOKAHEAD_NEG", sub_tokens))
            i = new_i
            continue
        elif c == "\\" and i + 1 < n:
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
                current_alt.append(("LITERAL", pattern[j]))
                i = j + 1
                continue
        elif c == ".":
            current_alt.append(("DOT", None))
            i += 1
        elif c == "[":
            j = i + 1
            neg = False
            if j < n and pattern[j] == "^":
                neg = True
                j += 1
            chars = []
            while j < n and pattern[j] != "]":
                if pattern[j] == "\\" and j + 1 < n:
                    chars.append(pattern[j + 1])
                    j += 2
                else:
                    chars.append(pattern[j])
                    j += 1
            if j == n:
                raise ValueError("Unclosed character class")
            val = "".join(chars)
            current_alt.append(("NEG_CLASS" if neg else "CLASS", val))
            i = j + 1
        elif c == "^":
            current_alt.append(("START", None))
            i += 1
        elif c == "$":
            current_alt.append(("END", None))
            i += 1
        elif c == "+":
            if not current_alt:
                raise ValueError("Nothing to repeat for +")
            prev = current_alt.pop()
            current_alt.append(("PLUS", prev))
            i += 1
        elif c == "?":
            if not current_alt:
                raise ValueError("Nothing to repeat for ?")
            prev = current_alt.pop()
            current_alt.append(("QUESTION", prev))
            i += 1
        elif c == "|":
            alts.append([])
            current_alt = alts[-1]
            i += 1
        elif c == "(":
            group_id = next_group[0]
            next_group[0] += 1
            sub_alts, new_i, next_group = parse_subpattern(pattern, i + 1, expect_close=True, next_group=next_group)
            sub_tokens = sub_alts[0] if len(sub_alts) == 1 else [("OR", sub_alts)]
            current_alt.append(("CAPTURE", (group_id, sub_tokens)))
            i = new_i
        elif c == ")":
            if not expect_close:
                current_alt.append(("LITERAL", ")"))
                i += 1
            else:
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
    return [("OR", alts)] if len(alts) > 1 else alts[0]

def match_here(tokens, s, idx, captures, open_groups):
    n = len(s)
    if not tokens:
        return idx, captures

    ttype, val = tokens[0]

    if ttype == "START" and idx != 0:
        return None
    if ttype == "END" and idx != n:
        return None
    if ttype in {"LITERAL", "DOT", "DIGIT", "WORD", "CLASS", "NEG_CLASS"}:
        if idx >= n or not match_token((ttype, val), s[idx]):
            return None
        return match_here(tokens[1:], s, idx + 1, captures, open_groups)
    if ttype == "BACKREF":
        group_num = val
        if group_num in captures:
            cap_start, cap_end = captures[group_num]
            captured_str = s[cap_start:cap_end]
            if s[idx:idx + len(captured_str)] != captured_str:
                return None
            return match_here(tokens[1:], s, idx + len(captured_str), captures, open_groups)
        elif group_num in open_groups:
            cap_start = open_groups[group_num]
            plen = idx - cap_start
            if s[idx:idx + plen] != s[cap_start:cap_start + plen]:
                return None
            return match_here(tokens[1:], s, idx + plen, captures, open_groups)
        else:
            return None
    if ttype == "CAPTURE":
        group_id, sub_tokens = val
        new_open = open_groups.copy()
        new_open[group_id] = idx
        sub_res = match_here(sub_tokens, s, idx, captures, new_open)
        if sub_res is None:
            return None
        sub_pos, sub_caps = sub_res
        new_caps = sub_caps.copy()
        new_caps[group_id] = (idx, sub_pos)
        new_open.pop(group_id, None)
        return match_here(tokens[1:], s, sub_pos, new_caps, new_open)
    if ttype == "OR":
        for alt in val:
            alt_res = match_here(alt, s, idx, captures, open_groups)
            if alt_res:
                rest_res = match_here(tokens[1:], s, alt_res[0], alt_res[1], open_groups)
                if rest_res:
                    return rest_res
        return None
    if ttype == "PLUS":
        inner = val
        min_res = match_here([inner], s, idx, captures, open_groups)
        if not min_res:
            return None
        pos, caps = min_res
        stack = [(pos, caps)]
        while True:
            next_res = match_here([inner], s, pos, caps, open_groups)
            if not next_res:
                break
            pos, caps = next_res
            stack.append((pos, caps))
        for p, c in reversed(stack):
            rest = match_here(tokens[1:], s, p, c, open_groups)
            if rest:
                return rest
        return None
    if ttype == "QUESTION":
        inner = val
        one = match_here([inner], s, idx, captures, open_groups)
        if one:
            rest = match_here(tokens[1:], s, one[0], one[1], open_groups)
            if rest:
                return rest
        return match_here(tokens[1:], s, idx, captures, open_groups)
    if ttype == "LOOKAHEAD_POS":
        if not match_here(val, s, idx, captures, open_groups):
            return None
        return match_here(tokens[1:], s, idx, captures, open_groups)
    if ttype == "LOOKAHEAD_NEG":
        if match_here(val, s, idx, captures, open_groups):
            return None
        return match_here(tokens[1:], s, idx, captures, open_groups)
    return None

def match(tokens, s):
    if tokens and tokens[0][0] == "START":
        res = match_here(tokens, s, 0, {}, {})