import sys
import re

def match_pattern(input_line, pattern):
    # Handle anchors
    if pattern.startswith("^"):
        return re.match(pattern, input_line) is not None
    if pattern.endswith("$"):
        return re.search(pattern + "$", input_line) is not None

    # Handle basic regex with backreferences and grouping
    try:
        return re.search(pattern, input_line) is not None
    except re.error:
        # Custom handling for simplified engine
        return custom_match(input_line, pattern)

def custom_match(input_line, pattern):
    # Only handle one capture group and one backreference for now
    if "(" in pattern and ")" in pattern and "\\1" in pattern:
        group_pat = pattern[pattern.index("(")+1:pattern.index(")")]
        before = pattern[:pattern.index("(")]
        after = pattern[pattern.index(")")+1:]

        # Split alternation if exists
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

    # fallback to direct regex
    return re.search(pattern, input_line) is not None

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] != "-E":
        print("Usage: ./your_program.sh -E <pattern>")
        sys.exit(1)

    pattern = sys.argv[2]
    input_text = sys.stdin.read()

    if match_pattern(input_text, pattern):
        sys.exit(0)
    else:
        sys.exit(1)
