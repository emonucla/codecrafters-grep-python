#!/usr/bin/env python3
"""
Robust grep-like tool with recursive (-r) and -E pattern support.

This file implements a small CLI that behaves similar to GNU grep for the
purposes of the codecrafters exercises. It tries to be forgiving when run
without arguments (it will run internal tests so the script doesn't just
exit with SystemExit:1 in interactive environments).

Supported features (sufficient for the current task):
- -E <pattern> : use a regular expression pattern (Python's `re` semantics)
- -r : recursively search directories
- multiple files: prints filename:line for matches across multiple files
- single file: prints lines without filename prefix (matches grep behavior)

The script is defensive about errors (unreadable files are skipped).

"""

import sys
import os
import re
import tempfile
import io
import contextlib
from typing import List


def regex_matches(pattern: str, line: str) -> bool:
    """Return True if the regex pattern matches anywhere in the line.
    Invalid patterns return False (we treat them as non-matching rather than crashing).
    """
    try:
        return re.search(pattern, line) is not None
    except re.error:
        return False


def grep_in_file(path: str, pattern: str, prefix_filename: bool = False, display_name: str = None) -> bool:
    """Search a single file line-by-line.

    - path: filesystem path used to open the file
    - pattern: regex pattern
    - prefix_filename: if True, print matches as "display_name:line"
    - display_name: string used when prefixing; if None, uses `path`

    Returns True if any matches were printed; False otherwise.
    """
    if display_name is None:
        display_name = path

    matched = False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if regex_matches(pattern, line):
                    if prefix_filename:
                        print(f"{display_name}:{line}")
                    else:
                        print(line)
                    matched = True
    except Exception:
        # Skip unreadable files silently (mirrors typical grep behavior).
        pass
    return matched


def grep_in_directory(dirname: str, pattern: str) -> bool:
    """Recursively search `dirname`. Print matches as "<relative>:line".

    The printed file path is relative to the parent of the directory passed
    (so passing 'dir/' results in prefixes like 'dir/file.txt'). This matches
    the examples provided in the task description.
    """
    matched = False
    # Determine the start directory for relpath calculations: the parent of dirname
    # so that the printed paths include the directory name itself (e.g. 'dir/...').
    start_base = os.path.dirname(os.path.abspath(dirname.rstrip(os.sep)))

    for root, _, files in os.walk(dirname):
        for fname in files:
            fpath = os.path.join(root, fname)
            # display path relative to start_base (so 'dir/...' is printed)
            display = os.path.relpath(fpath, start=start_base)
            if grep_in_file(fpath, pattern, prefix_filename=True, display_name=display):
                matched = True
    return matched


# --- internal tests ---------------------------------------------------------

def run_tests() -> int:
    """Run a few basic unit-style checks. Returns 0 on success else 1.

    Tests create temporary files / directories to check file and recursive
    behavior. This helps avoid surprising SystemExit when the script is
    executed without arguments in interactive environments.
    """
    failed = 0

    def assert_eq(a, b, msg=""):
        nonlocal failed
        if a != b:
            print("ASSERT FAIL:", a, "!=", b, msg)
            failed += 1

    # regex matching basics
    assert_eq(regex_matches(r"apple", "apple"), True, "literal")
    assert_eq(regex_matches(r"appl.*", "apple"), True, "dot-star")
    assert_eq(regex_matches(r"carrot", "apple"), False, "no-match")
    assert_eq(regex_matches(r"^start", "start of line"), True, "anchor start")
    assert_eq(regex_matches(r"end$", "the end"), True, "anchor end")
    assert_eq(regex_matches(r"\\d+", "12345"), True, "digit class")

    # file-based tests
    td = tempfile.mkdtemp(prefix="grep_test_")
    try:
        # create files and directories
        f1 = os.path.join(td, "fruits.txt")
        with open(f1, "w", encoding="utf-8") as fh:
            fh.write("pear\nstrawberry\n")

        sub = os.path.join(td, "subdir")
        os.makedirs(sub, exist_ok=True)
        f2 = os.path.join(sub, "vegetables.txt")
        with open(f2, "w", encoding="utf-8") as fh:
            fh.write("celery\ncarrot\n")

        f3 = os.path.join(td, "vegetables.txt")
        with open(f3, "w", encoding="utf-8") as fh:
            fh.write("cucumber\ncorn\n")

        # capture stdout for grep_in_file
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = grep_in_file(f1, r"pear")
        out = buf.getvalue().strip().splitlines()
        assert_eq(m, True, "grep_in_file matched flag")
        assert_eq(out, ["pear"], "grep_in_file printed line")

        # multiple file grep (single file, no prefix)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = grep_in_file(f3, r"cucumber")
        out = buf.getvalue().strip().splitlines()
        assert_eq(m, True, "single file match")
        assert_eq(out, ["cucumber"], "single file printed without prefix")

        # recursive grep
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = grep_in_directory(td, r".*er")
        out = [line.strip() for line in buf.getvalue().splitlines() if line.strip()]
        # Expect 3 matches but order isn't guaranteed; check membership
        expected = {os.path.join(os.path.basename(td), "fruits.txt") + ":strawberry",
                    os.path.join(os.path.basename(td), "subdir", "vegetables.txt") + ":celery",
                    os.path.join(os.path.basename(td), "vegetables.txt") + ":cucumber"}
        assert_eq(set(out) == expected, True, f"recursive output mismatch: got={out} expected={expected}")
        assert_eq(m, True, "recursive returned True")

    finally:
        # clean up created files/directories
        try:
            for root, dirs, files in os.walk(td, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(td)
        except Exception:
            pass

    if failed:
        print(f"{failed} test(s) failed")
        return 1

    print("All internal tests passed")
    return 0


# --- CLI -------------------------------------------------------------------

def usage():
    print("Usage: ./your_program.py [-r] -E <pattern> [file_or_dir ...]", file=sys.stderr)


def main(argv: List[str] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # No arguments: run internal tests so the script doesn't simply exit(1)
    if not argv:
        return run_tests()

    # Parse flags: accept -r optionally. Remove all occurrences of '-r' from argv.
    recursive = False
    while "-r" in argv:
        recursive = True
        argv = [a for a in argv if a != "-r"]

    # Expect -E <pattern>
    if len(argv) < 2 or argv[0] != "-E":
        usage()
        return 2

    pattern = argv[1]
    targets = argv[2:]

    # If recursive, require at least one target (directory or file)
    if recursive:
        if not targets:
            usage()
            return 2
        matched_any = False
        for target in targets:
            # If target is a directory, walk it
            if os.path.isdir(target):
                if grep_in_directory(target, pattern):
                    matched_any = True
            elif os.path.isfile(target):
                # Treat file passed with -r as regular file; print filename:line
                if grep_in_file(target, pattern, prefix_filename=True, display_name=target):
                    matched_any = True
            else:
                # skip non-existing entries
                continue
        return 0 if matched_any else 1

    # Non-recursive: search files or stdin
    if not targets:
        # read from stdin
        matched_any = False
        for raw in sys.stdin:
            line = raw.rstrip("\n")
            if regex_matches(pattern, line):
                print(line)
                matched_any = True
        return 0 if matched_any else 1

    # If one file: print lines without filename prefix
    if len(targets) == 1:
        matched = grep_in_file(targets[0], pattern, prefix_filename=False)
        return 0 if matched else 1

    # Multiple files: prefix each printed line with filename:
    matched_any = False
    for fname in targets:
        if grep_in_file(fname, pattern, prefix_filename=True, display_name=fname):
            matched_any = True
    return 0 if matched_any else 1


if __name__ == "__main__":
    code = main()
    sys.exit(code)
