#!/usr/bin/env python3
import os
import re
import sys

def grep_file(pattern, filename, prefix_filename=True):
    """Search for pattern in a single file. Return list of formatted matching lines."""
    matches = []
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.rstrip("\n")
                if re.search(pattern, line):
                    if prefix_filename:
                        matches.append(f"{filename}:{line}")
                    else:
                        matches.append(line)
    except (IOError, OSError):
        # Skip unreadable files
        pass
    return matches


def grep_directory(pattern, directory):
    """Recursively search through a directory."""
    matches = []
    for root, _, files in os.walk(directory):
        for fname in files:
            path = os.path.join(root, fname)
            matches.extend(grep_file(pattern, path, prefix_filename=True))
    return matches


def main(argv=None):
    if argv is None:
        argv = sys.argv

    # Usage: ./your_program.sh [-r] -E <pattern> [file...|dir...]
    recursive = False

    # Handle flags
    args = argv[1:]
    if not args:
        print("Usage: ./your_program.sh [-r] -E <pattern> [file...|dir...]")
        return 2

    if "-r" in args:
        recursive = True
        args.remove("-r")

    if len(args) < 2 or args[0] != "-E":
        print("Usage: ./your_program.sh [-r] -E <pattern> [file...|dir...]")
        return 2

    pattern = args[1]
    targets = args[2:]

    if not targets:
        # No files/dirs provided, read from stdin
        line = sys.stdin.read().rstrip("\n")
        if re.search(pattern, line):
            print(line)
            return 0
        return 1

    all_matches = []
    multiple_files = len(targets) > 1 or recursive

    for target in targets:
        if recursive and os.path.isdir(target):
            all_matches.extend(grep_directory(pattern, target))
        elif os.path.isfile(target):
            all_matches.extend(grep_file(pattern, target, prefix_filename=multiple_files))
        else:
            # Ignore invalid paths
            pass

    if all_matches:
        for m in all_matches:
            print(m)
        return 0
    return 1


if __name__ == "__main__":
    code = main()
    try:
        sys.exit(code)
    except SystemExit:
        # Suppress traceback in interactive mode
        if hasattr(sys, "ps1"):  # interactive shell (like notebooks/REPL)
            print(f"[Exited with code {code}]")
        else:
            raise
