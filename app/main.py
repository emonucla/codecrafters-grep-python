import sys
import re

def match_pattern(input_line, pattern):
    # Handle anchors quickly
    if pattern.startswith("^") or pattern.endswith("$"):
        return re.match(pattern, input_line) is not None

    # Try built-in regex first
    try:
        return re.search(pattern, input_line) is not None
    except re.error:
        # Fall back to custom simplified handling
        return custom_match(input_line, pattern)

def custom_match(input_line, pattern):
    # Handle single capturing group with backreference
    if "(" in pattern and ")" in pattern and "\\1" in pattern:
        group_start = pattern.index("(")
        group_end = pattern.index(")")
        group_pat = pattern[group_start+1:group_end]

        before = pattern[:group_start]
        after = pattern[group_end+1:]

        # Support alternation in the group
        options = group_pat.split("|")

        for opt in options:
            subpat = before + f"({opt})" + after
            m = re.search(subpat, input_line)
            if m:
                captured = m.group(1)
                # Replace \1 with captured value
                new_pat = before + captured + after.replace("\\1", captured)
                if re.search(new_pat, input_line):
                    return True
        return False

    # Otherwise fallback
    return re.search(pattern, input_line) is not None

def main():
    if len(sys.argv) < 3 or sys.argv[1] != "-E":
        print("Usage: ./your_program.sh -E <pattern>")
        sys.exit(1)

    pattern = sys.argv[2]
    input_text = sys.stdin.read()

    if match_pattern(input_text, pattern):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
