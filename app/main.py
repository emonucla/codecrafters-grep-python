def match_pattern(input_line, pattern):
    groups = {}  # store group_num -> matched string
    
    def expand_backrefs(s):
        # replace \1, \2, ... with stored values
        i = 1
        while f"\\{i}" in s:
            if i in groups:
                s = s.replace(f"\\{i}", groups[i])
            i += 1
        return s

    def match_group(subpattern, text):
        # recursively match groups
        expanded = expand_backrefs(subpattern)
        if text.startswith(expanded):
            return expanded
        return None

    # Walk through pattern, handle capturing groups
    # Example: ('(cat) and \2') is the same as \1
    # Group 2 → "cat"
    # Group 1 → "'cat and cat'"
