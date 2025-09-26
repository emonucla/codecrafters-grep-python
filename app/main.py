import sys

def tokenize(pattern: str):
    tokens = []
    i = 0
    # Handle ^ at beginning
    if pattern.startswith("^"):
        tokens.append(("ANCHOR_START", None))
        i = 1
    while i < len(pattern):
        if pattern[i] == "\\" and i + 1 < len(pattern):
            tokens.append(("ESC", pattern[i+1]))
            i += 2
        elif pattern[i] == "[":
            end = pattern.find("]", i)
            if end == -1:
                raise RuntimeError("Unclosed [ in pattern")
            content = pattern[i+1:end]
            if content.startswith("^"):
                tokens.append(("NEG_GROUP", set(content[1:])))
            else:
                tokens.append(("POS_GROUP", set(content)))
            i = end + 1
        elif pattern[i] == "$" and i == len(pattern) - 1:
            tokens.append(("ANCHOR_END", None))
            i += 1
        else:
            tokens.append(("LIT", pattern[i]))
            i += 1
    return tokens

def match_token(token, ch):
    ttype, val = token
    if ttype == "LIT":
        return ch == val
    if ttype == "ESC":
        if val == "d":
            return ch.isdigit()
        if val == "w":
            return ch.isalnum() or ch == "_"
        return ch == val
    if ttype == "POS_GROUP":
        return ch in val
    if ttype == "NEG_GROUP":
        return ch not in val
    raise RuntimeError(f"Unexpected token type: {ttype}")

def match_pattern(input_line, pattern):
    tokens = tokenize(pattern)

    anchored_start = tokens and tokens[0][0] == "ANCHOR_START"
    anchored_end   = tokens and tokens[-1][0] == "ANCHOR_END"

    if anchored_start:
        tokens = tokens[1:]
    if anchored_end:
        tokens = tokens[:-1]

    n, m = len(input_line), len(tokens)

    if anchored_start and anchored_end:
        # must match full string
        if m != n:
            return False
        for j, token in enumerate(tokens):
            if not match_token(token, input_line[j]):
                return False
        return True

    if anchored_start:
        if m > n:
            return False
        for j, token in enumerate(tokens):
            if not match_token(token, input_line[j]):
                return False
        return True

    if anchored_end:
        if m > n:
            return False
        start = n - m
        for j, token in enumerate(tokens):
            if not match_token(token, input_line[start + j]):
                return False
        return True

    # No anchors: search anywhere
    for start in range(n - m + 1):
        ok = True
        for j, token in enumerate(tokens):
            if not match_token(token, input_line[start + j]):
                ok = False
                break
        if ok:
            return True
    return False

def main():
    if len(sys.argv) < 3 or sys.argv[1] != "-E":
        print("Expected first argument to be '-E'")
        exit(1)

    pattern = sys.argv[2]
    input_line = sys.stdin.read()

    print("Logs from your program will appear here!", file=sys.stderr)

    if match_pattern(input_line, pattern):
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    main()
