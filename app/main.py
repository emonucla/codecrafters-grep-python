import sys

# ---------------------------
# Tokenizer
# ---------------------------
def tokenize(pattern):
    tokens = []
    i = 0
    group_id = 1
    while i < len(pattern):
        c = pattern[i]
        if c == "(":
            sub, j, group_id = parse_group(pattern, i + 1, group_id)
            tokens.append(("CAPTURE", (group_id, sub)))
            i = j + 1
            group_id += 1
        elif c == "\\":
            if i + 1 < len(pattern) and pattern[i+1].isdigit():
                tokens.append(("BACKREF", int(pattern[i+1])))
                i += 2
            else:
                tokens.append(("LITERAL", pattern[i+1]))
                i += 2
        else:
            tokens.append(("LITERAL", c))
            i += 1
    return tokens

def parse_group(pat, start, group_id):
    tokens = []
    i = start
    while i < len(pat) and pat[i] != ")":
        c = pat[i]
        if c == "(":
            sub, j, group_id = parse_group(pat, i + 1, group_id)
            tokens.append(("CAPTURE", (group_id, sub)))
            i = j + 1
            group_id += 1
        elif c == "\\":
            if i + 1 < len(pat) and pat[i+1].isdigit():
                tokens.append(("BACKREF", int(pat[i+1])))
                i += 2
            else:
                tokens.append(("LITERAL", pat[i+1]))
                i += 2
        else:
            tokens.append(("LITERAL", c))
            i += 1
    return tokens, i, group_id

# ---------------------------
# Backreference resolver
# ---------------------------
def expand_tokens(tokens, captures):
    out = []
    for ttype, val in tokens:
        if ttype == "LITERAL":
            out.append(val)
        elif ttype == "BACKREF":
            resolved = resolve_backref(val, captures)
            if resolved is None:
                return None
            out.append(resolved)
        elif ttype == "CAPTURE":
            gid, sub = val
            resolved = resolve_backref(gid, captures)
            if resolved is None:
                return None
            out.append(resolved)
    return "".join(out)

def resolve_backref(n, captures):
    cap = captures.get(n)
    if cap is None:
        return None
    if isinstance(cap, str):
        return cap
    # structured capture
    return expand_tokens(cap["tokens"], captures)

# ---------------------------
# Matcher
# ---------------------------
def match_here(tokens, s, idx, captures):
    if not tokens:
        return (idx, captures)

    ttype, val = tokens[0]

    if ttype == "LITERAL":
        if idx < len(s) and s[idx] == val:
            return match_here(tokens[1:], s, idx + 1, captures)
        return None

    if ttype == "BACKREF":
        resolved = resolve_backref(val, captures)
        if resolved is None:
            return None
        if s.startswith(resolved, idx):
            return match_here(tokens[1:], s, idx + len(resolved), captures)
        return None

    if ttype == "CAPTURE":
        gid, sub_tokens = val
        sub_res = match_here(sub_tokens, s, idx, captures)
        if sub_res is None:
            return None
        sub_pos, sub_caps = sub_res
        new_caps = sub_caps.copy()
        # store lazily
        new_caps[gid] = {"tokens": sub_tokens, "span": (idx, sub_pos)}
        return match_here(tokens[1:], s, sub_pos, new_caps)

    return None

def match(tokens, s):
    res = match_here(tokens, s, 0, {})
    return res is not None and res[0] == len(s)

# ---------------------------
# Entry
# ---------------------------
def main():
    if len(sys.argv) < 3 or sys.argv[1] != "-E":
        print("Usage: ./your_program.sh -E <pattern>")
        sys.exit(1)

    pattern = sys.argv[2]
    text = sys.stdin.read()

    tokens = tokenize(pattern)
    if match(tokens, text):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
