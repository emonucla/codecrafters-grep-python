#!/usr/bin/env python3
import sys, string, os

DIGITS = string.digits
WORD = DIGITS + string.ascii_letters + "_"


def find_close(p, i=0):
    depth = 0
    in_class = False
    esc = False
    while i < len(p):
        c = p[i]
        if esc:
            esc = False
        elif c == "\\":
            esc = True
        elif in_class:
            if c == "]":
                in_class = False
        else:
            if c == "[":
                in_class = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError("unbalanced ()")


def split_alts(p):
    out = []
    start = 0
    depth = 0
    in_class = False
    esc = False
    for i, c in enumerate(p):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if in_class:
            if c == "]":
                in_class = False
            continue
        if c == "[":
            in_class = True
            continue
        if c == "(":
            depth += 1
            continue
        if c == ")":
            depth -= 1
            continue
        if c == "|" and depth == 0:
            out.append(p[start:i])
            start = i + 1
    out.append(p[start:])
    return out


def count_groups(p):
    n = 0
    in_class = False
    esc = False
    for c in p:
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if in_class:
            if c == "]":
                in_class = False
            continue
        if c == "[":
            in_class = True
            continue
        if c == "(":
            n += 1
    return n


def next_atom(p):
    if not p:
        return None, ""
    if p[0] == ".":
        return (lambda ch: ch != "\n"), p[1:]
    if p.startswith("[^]"):
        return (lambda ch: True), p[3:]
    if p.startswith("[^"):
        j = p.index("]")
        bad = set(p[2:j])
        return (lambda ch, bad=bad: ch not in bad), p[j + 1 :]
    if p[0] == "[":
        j = p.index("]")
        good = set(p[1:j])
        return (lambda ch, good=good: ch in good), p[j + 1 :]
    if p[0] == "\\":
        if len(p) < 2:
            return (lambda ch: ch == "\\"), ""
        t = p[1]
        if t == "d":
            return (lambda ch: ch in DIGITS), p[2:]
        elif t == "w":
            return (lambda ch: ch in WORD), p[2:]
        else:
            return (lambda ch, t=t: ch == t), p[2:]
    c = p[0]
    return (lambda ch, c=c: ch == c), p[1:]


def try_backref(s, p, caps):
    if not p.startswith("\\") or len(p) < 2 or not p[1].isdigit():
        return None
    j = 2
    while j < len(p) and p[j].isdigit():
        j += 1
    idx = int(p[1:j]) - 1
    if idx < 0 or idx >= len(caps) or caps[idx] is None:
        return False
    g = caps[idx]
    if not s.startswith(g):
        return False
    return s[len(g) :], p[j:]


def gen(s, p, caps, gi):
    if p == "":
        yield s, caps
        return

    br = try_backref(s, p, caps)
    if br is False:
        return
    if br is not None:
        s2, p2 = br
        yield from gen(s2, p2, caps, gi)
        return

    if p[0] == "(":
        j = find_close(p, 0)
        body, rest = p[1:j], p[j + 1 :]
        q = rest[0] if rest else ""
        this_id = gi
        inner_start = gi + 1
        span = 1 + count_groups(body)

        def gen_body(s0, caps0):
            for alt in split_alts(body):
                cc = caps0[:] + [None] * max(0, this_id + 1 - len(caps0))
                for out_s, cc2 in gen(s0, alt, cc, inner_start):
                    cc3 = cc2[:] + [None] * max(0, this_id + 1 - len(cc2))
                    cc3[this_id] = s0[: len(s0) - len(out_s)]
                    yield out_s, cc3

        if q == "+":
            rest2 = rest[1:]
            stack = list(gen_body(s, caps))
            while stack:
                out_s, ccx = stack.pop()
                yield from gen(out_s, rest2, ccx, gi + span)
                if len(out_s) < len(s):
                    for out2, cc2 in gen_body(out_s, ccx):
                        if len(out2) != len(out_s):
                            stack.append((out2, cc2))
            return

        if q == "?":
            rest2 = rest[1:]
            for out_s, ccx in gen_body(s, caps):
                yield from gen(out_s, rest2, ccx, gi + span)
            yield from gen(s, rest2, caps[:], gi + span)
            return

        for out_s, ccx in gen_body(s, caps):
            yield from gen(out_s, rest, ccx, gi + span)
        return

    f, rest = next_atom(p)
    if f is None:
        return
    q = rest[0] if rest else ""

    if q == "+":
        tail = rest[1:]
        if not s or not f(s[0]):
            return
        i = 1
        while i <= len(s) and f(s[i - 1]):
            i += 1
        i -= 1
        for k in range(i, 0, -1):
            yield from gen(s[k:], tail, caps[:], gi)
        return

    if q == "?":
        tail = rest[1:]
        if s and f(s[0]):
            yield from gen(s[1:], tail, caps[:], gi)
        yield from gen(s, tail, caps[:], gi)
        return

    if not s or not f(s[0]):
        return
    yield from gen(s[1:], rest, caps, gi)


def matches(s, p):
    alts = split_alts(p)
    if len(alts) > 1:
        return any(matches(s, a) for a in alts)
    if p.startswith("^") and p.endswith("$"):
        return any(out == "" for out, _ in gen(s, p[1:-1], [], 0))
    if p.endswith("$"):
        core = p[:-1]
        for i in range(len(s) + 1):
            if any(out == "" for out, _ in gen(s[i:], core, [], 0)):
                return True
        return False
    if p.startswith("^"):
        return any(True for _ in gen(s, p[1:], [], 0))
    for i in range(len(s) + 1):
        if any(True for _ in gen(s[i:], p, [], 0)):
            return True
    return False


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "-E":
        sys.exit(1)

    pat = sys.argv[2]

    # File mode
    if len(sys.argv) >= 4:
        try:
            with open(sys.argv[3], "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
        except Exception:
            sys.exit(1)

        matched = False
        for line in lines:
            if matches(line, pat):
                print(line)
                matched = True

        sys.exit(0 if matched else 1)

    # Stdin mode
    txt = sys.stdin.read()
    sys.exit(0 if matches(txt, pat) else 1)


if __name__ == "__main__":
    main()