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


def tokenize(pattern):
    """Convert pattern into tokens for matching."""
    tokens = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\" and i + 1 < len(pattern):
            nxt = pattern[i + 1]
            if nxt == "d":
                tokens.append(("DIGIT", None))
            elif nxt == "w":
                tokens.append(("WORD", None))
            else:
                tokens.append(("LITERAL", nxt))
            i += 2
        elif c == ".":
            tokens.append(("DOT", None))
            i += 1
        elif c == "[":
            j = i + 1
            neg = False
            if j < len(pattern) and pattern[j] == "^":
                neg = True
                j += 1
            chars = []
            while j < len(pattern) and pattern[j] != "]":
                chars.append(pattern[j])
                j += 1
            if neg:
                tokens.append(("NEG_CLASS", "".join(chars)))
            else:
                tokens.append(("CLASS", "".join(chars)))
            i = j + 1
        elif c == "^":
            tokens.append(("START", None))
            i += 1
        elif c == "$":
            tokens.append(("END", None))
            i += 1
        elif c == "+":
            if not tokens:
                raise ValueError("Nothing to repeat for +")
            prev = tokens.pop()
            tokens.append(("PLUS", prev))
            i += 1
        else:
            tokens.append(("LITERAL", c))
            i += 1
    return tokens


def match_here(tokens, s, idx):
    """Try matching tokens starting at s[idx:]."""
    if not tokens:
        return idx == len(s)

    ttype, val = tokens[0]

    if ttype == "START":
        return idx == 0 and match_here(tokens[1:], s, idx)

    if ttype == "END":
        return idx == len(s) and match_here(tokens[1:], s, idx)

    if ttype == "PLUS":
        inner = val
        # Require at least one match
        if idx >= len(s) or not match_token(inner, s[idx]):
            return False

        j = idx
        while j < len(s) and match_token(inner, s[j]):
            j += 1

        # Try all splits (greedy but with backtracking)
        for k in range(j, idx, -1):
            if match_here(tokens[1:], s, k):
                return True
        return False

    if idx < len(s) and match_token((ttype, val), s[idx]):
        return match_here(tokens[1:], s, idx + 1)

    return False


def match(tokens, s):
    if tokens and tokens[0][0] == "START":
        return match_here(tokens, s, 0)
    for i in range(len(s) + 1):
        if match_here(tokens, s, i):
            return True
    return False


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "-E":
        print("Usage: ./your_program.sh -E <pattern>")
        sys.exit(1)

    pattern = sys.argv[2]
    input_text = sys.stdin.read()

    tokens = tokenize(pattern)
    if match(tokens, input_text):
        sys.exit(0)
    else:
        sys.exit(1)
