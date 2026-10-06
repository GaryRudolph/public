#!/usr/bin/env python3
"""Merge a template's keys into a JSON settings file, mechanically.

Used by the personal-repo-baseline skill to apply
templates/claude-settings.json to a repo's .claude/settings.json. It makes
no decisions: which differing values to replace is the agent's call (after
asking), passed in with --take.

Rules:
  - A key the target lacks is added with the template's value.
  - An object in both is merged key by key, recursively.
  - Any other value in both is left as the target has it, unless --take
    names its dotted path (for example attribution.commit). Each one left
    alone is listed on stderr as "kept".
  - No key is ever removed.
  - "$schema" goes first. Other keys keep their order; new keys follow in
    template order.
  - Output is JSON with 2-space indents and a trailing newline.

Without --write it changes nothing: it prints the merged file, or with
--diff a unified diff against the current one. With --write it writes the
target (creating its directory) only when the content changes.

Exit status: 0 on success, 1 when a file can't be read or isn't a JSON
object without duplicate keys (the target is left untouched), 2 on a usage
error, including a --take path that names no differing value.
"""

import argparse
import difflib
import json
import os
import sys
import tempfile

SCHEMA_KEY = "$schema"


def load_object(path, missing_ok):
    if missing_ok and not os.path.exists(path):
        return {}, ""
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except OSError as exc:
        raise SystemExit(f"merge_settings: can't read {path}: {exc}") from None
    dupes = []

    def hook(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                dupes.append(key)
            seen.add(key)
        return dict(pairs)

    try:
        data = json.loads(text, object_pairs_hook=hook)
    except ValueError as exc:
        raise SystemExit(f"merge_settings: {path} isn't valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"merge_settings: {path} isn't a JSON object")
    if dupes:
        raise SystemExit(f"merge_settings: {path} has duplicate keys: {', '.join(dupes)}")
    return data, text


def merge(target, template, take, prefix, kept, taken):
    out = dict(target)
    for key, value in template.items():
        path = f"{prefix}{key}"
        if key not in out:
            out[key] = value
        elif isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = merge(out[key], value, take, f"{path}.", kept, taken)
        elif out[key] != value:
            if path in take:
                out[key] = value
                taken.add(path)
            else:
                kept.append((path, out[key], value))
    return out


def schema_first(data):
    if SCHEMA_KEY not in data:
        return data
    return {SCHEMA_KEY: data[SCHEMA_KEY], **{k: v for k, v in data.items() if k != SCHEMA_KEY}}


def write_atomic(path, text):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o644
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".merge_settings.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("template")
    parser.add_argument("target")
    parser.add_argument("--take", action="append", default=[], metavar="PATH",
                        help="use the template's value at this dotted path")
    out_mode = parser.add_mutually_exclusive_group()
    out_mode.add_argument("--diff", action="store_true", help="print a unified diff instead of the file")
    out_mode.add_argument("--write", action="store_true", help="write the target")
    args = parser.parse_args(argv)

    try:
        template, _ = load_object(args.template, missing_ok=False)
        target, before = load_object(args.target, missing_ok=True)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1

    kept, taken = [], set()
    merged = schema_first(merge(target, template, set(args.take), "", kept, taken))
    unused = [p for p in args.take if p not in taken]
    if unused:
        print(f"merge_settings: --take names no differing value: {', '.join(unused)}", file=sys.stderr)
        return 2

    after = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    for path, have, want in kept:
        print(f"kept: {path}: {json.dumps(have)} (template: {json.dumps(want)})", file=sys.stderr)
    changed = after != before
    if args.write:
        if changed:
            write_atomic(args.target, after)
        print(f"{'wrote' if changed else 'unchanged'}: {args.target}", file=sys.stderr)
    elif args.diff:
        sys.stdout.writelines(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=args.target if before else "/dev/null", tofile=args.target))
        print(f"{'would change' if changed else 'unchanged'}: {args.target}", file=sys.stderr)
    else:
        sys.stdout.write(after)
        print(f"{'would change' if changed else 'unchanged'}: {args.target}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
