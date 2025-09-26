import sys

# import pyparsing - available if you need it!
# import lark - available if you need it!


def match_pattern(input_line, pattern):
    # Handle \d (digit class)
    if pattern == r"\d":
        return any(ch.isdigit() for ch in input_line)
    
     # Handle \w (word character class: a-z, A-Z, 0-9, _)
    if pattern == r"\w":
        return any(ch.isalnum() or ch == "_" for ch in input_line)
    
    # Handle negative character groups like [^abc]
    if pattern.startswith("[^") and pattern.endswith("]"):
        forbidden = set(pattern[2:-1])
        return any(ch not in forbidden for ch in input_line)
    
    # Handle positive character groups like [abc]
    if pattern.startswith("[") and pattern.endswith("]"):
        allowed = set(pattern[1:-1])  # characters inside brackets
        return any(ch in allowed for ch in input_line)

    # Handle single literal character
    if len(pattern) == 1:
        return pattern in input_line
    else:
        raise RuntimeError(f"Unhandled pattern: {pattern}")


def main():
    pattern = sys.argv[2]
    input_line = sys.stdin.read()

    if sys.argv[1] != "-E":
        print("Expected first argument to be '-E'")
        exit(1)

    # You can use print statements as follows for debugging, they'll be visible when running tests.
    print("Logs from your program will appear here!", file=sys.stderr)

    # Uncomment this block to pass the first stage
    if match_pattern(input_line, pattern):
         exit(0)
    else:
         exit(1)


if __name__ == "__main__":
    main()
