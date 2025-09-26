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
        elif pattern[i] == "+":
            if not tokens:
                raise RuntimeError("Nothing before + quantifier")
            prev = tokens.pop()
            tokens.append(("PLUS", prev))
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

def match_here(tokens, s, idx):
    """Try to match tokens against s starting at position idx."""
    if not tokens:
        return idx == len(s)  # must consume full string if at end

    ttype, val = tokens[0]

    # End anchor
    if ttype == "ANCHOR_END":
        return idx == len(s)

    # PLUS quantifier
    if ttype == "PLUS":
        inner = val
        # Must match at least once
        if idx >= len(s) or not match_token(inner, s[idx]):
            return False
        j = idx
        # Consume as many as possible
        while j < len(s) and match_token(inner, s[j]):
            # Try rest of pattern after consuming k chars
            if match_here(tokens[1:], s, j + 1):
                return True
            j += 1
        return False

    # Normal token
    if idx < len(s) and match_token((ttype, val), s[idx]):
        return match_here(tokens[1:], s, idx + 1)
    return False

def match_pattern(input_line, pattern):
    tokens = tokenize(pattern)

    anchored_start = tokens and tokens[0][0] == "ANCHOR_START"
    if anchored_start:
        tokens = tokens[1:]
        return match_here(tokens, input_line, 0)

    # Unanchored: try all start positions
    for start in range(len(input_line) + 1):
        if match_here(tokens, input_line, start):
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
