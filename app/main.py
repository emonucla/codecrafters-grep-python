import sys

def main():
    args = sys.argv[1:]

    if len(args) < 2 or args[0] != "-E":
        sys.exit(1)

    pattern = args[1]
    filename = args[2] if len(args) > 2 else None

    if filename:
        with open(filename, "r") as f:
            line = f.read().rstrip("\n")
    else:
        line = sys.stdin.read()

    if match_pattern(line, pattern):   # <-- reuse your existing matcher
        print(line)
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
