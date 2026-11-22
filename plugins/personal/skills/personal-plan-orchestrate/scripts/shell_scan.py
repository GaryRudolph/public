"""What worker_guard.py and reviewer_guard.py share: where a command word may start in a Bash call, and which strings a
shell would run that a plain pass over the text masks.

Neither guard parses bash. Both are deny lists over regular expressions, so this module keeps each pattern
unambiguous (two ways to read one flag would make the match time exponential, and a hook that times out lets the call
through) and the guards set an alarm besides (see deadline()).

- START: a command word's position: the start, after a separator, a subshell or a substitution, past the shell's
  keywords and `{`, wrappers (sudo, env, command, exec, nohup, time, eval, timeout, nice, xargs) with their flags, and
  VAR=value assignments.
- join_continuations(): the text with each backslash-newline outside single quotes removed, as the shell reads it.
- bare(): the command with heredoc bodies and quoted strings set aside.
- inner_strings(): the strings a shell would run that bare() sets aside: the argument of `sh|bash|zsh -c`, the
  arguments of an `eval`, every $(...) and backtick body (an unquoted heredoc body included), and a find's -exec
  actions. Each is found at a command position of the text with its quoted strings masked, so quoted prose that merely
  mentions a command is not one.
- STDIN_SHELL: a shell that reads its commands from stdin, which nothing here can see.
"""

import re
import shlex
import signal
from collections import namedtuple

# Words that sit before the command word: wrappers that run what follows, and the shell's keywords and `{` that begin a
# command (`if make release; then ...`, `for d in a; do git push; done`, `{ git push; }`, `! git push`).
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
# The wrappers with flags of their own: the short flags that take a value, the long ones, and an operand pattern
# (timeout's duration). A flag cluster's first value letter takes the rest of the word as its value, or the next word
# when it ends the cluster (-s KILL, -rn 1; -IFILE is one word). A boolean flag takes none, so `xargs -r echo git push`
# prints text; -l, -i, -e and their long forms take only an attached optional value.
WRAPPER_FLAGS = {
    "timeout": ("sk", {"signal", "kill-after"}, r"\d+(?:\.\d+)?[smhd]?"),
    "nice": ("n", {"adjustment"}, None),
    "xargs": ("aEIJLnPsdRS", {"arg-file", "delimiter", "max-args", "max-chars", "max-procs", "process-slot-var"}, None),
    "sudo": ("ugCUhpRrT", {"user", "group", "chdir", "host", "prompt", "role", "type", "chroot", "other-user", "close-from"}, None),
    "env": ("uC", {"unset", "chdir"}, None),
}
# `command -v rm` looks a name up and runs nothing: these flags end the prefix.
LOOKUP_FLAGS = {"command": "vV"}
# Commands that may be named by path (/usr/bin/timeout); the keywords may not.
COMMAND_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "timeout", "nice", "xargs", "eval"}
SHELL_NAMES = r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)"
# A shell's own flags: a cluster ending in o or O takes an option name (-o pipefail, -euo pipefail), other clusters, and
# long flags (and `--`). The three are disjoint, so a flag has one reading.
SHELL_FLAG = r"(?:-(?!-)[A-Za-z]*[Oo]\s+\S+|-(?!-)(?![A-Za-z]*[Oo](?:\s|$))[A-Za-z]+|--[A-Za-z-]*)"


def _letters_before(letters):
    """A run of letters that are not value letters: the booleans ahead of a cluster's first value letter."""
    return rf"(?:(?![{letters}])[A-Za-z])*"


def _prefix_word(word):
    shorts, longs, operand = WRAPPER_FLAGS.get(word, ("", (), None))
    names = "|".join(sorted(longs))
    lookup = LOOKUP_FLAGS.get(word)
    alts = []
    if shorts:  # a cluster whose first value letter ends it takes the next word
        alts.append(rf"-(?!-){_letters_before(shorts)}[{shorts}]\s+\S+")
    if longs:
        alts.append(rf"--(?:{names})\s+\S+")
    # The boolean flags are what the two forms above are not, so no flag is readable both ways.
    skip_value = rf"(?!{_letters_before(shorts)}[{shorts}](?:\s|$))" if shorts else ""
    skip_lookup = rf"(?![A-Za-z]*[{lookup}])" if lookup else ""
    alts.append(rf"-(?!-){skip_value}{skip_lookup}\S+")
    alts.append(rf"--(?!(?:{names})(?:\s|$))\S*" if longs else r"--\S*")
    if operand:
        alts.append(operand)
    path = r"(?:\S*/)?" if word in COMMAND_WORDS else ""
    return path + re.escape(word) + r"(?:\s+(?:" + "|".join(alts) + r"))*\s+"


# What may sit between a separator and the command word: prefix words with their flags, and VAR=value assignments.
PREFIX = (r"(?:" + "|".join(_prefix_word(w) for w in sorted(PREFIX_WORDS | set(WRAPPER_FLAGS), key=len, reverse=True))
          + r"|[A-Za-z_]\w*=\S*\s+)*")
LEAD = r"(?:^|[;&|(`\n]|\$\()\s*"
START = LEAD + PREFIX

ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$")
SEPARATOR = re.compile(r"\|\||&&|[;|&()`\n]|\$\(")
HEREDOC = re.compile(r"(?<!<)(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:(?P<body>.*?)\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a $'...' string is the single-quoted one after its $

_WORD = r"(?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^\s;&|()<>'\"])+"  # one shell word: quoted and bare pieces side by side
# The argument of `sh -c`, whole: quoted pieces and bare text alike. Its flags are kept to see a no-exec -n.
SHELL_C = re.compile(START + SHELL_NAMES + r"(?P<flags>(?:\s+" + SHELL_FLAG + r")*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?)\s+(?P<arg>" + _WORD + ")")
SHELL_NO_EXEC = re.compile(r"(?:^|\s)-(?!-)[A-Za-z]*n[A-Za-z]*(?=\s|$)")
# eval joins its arguments and runs them, so every argument counts, quoted or not.
EVAL_ARGS = re.compile(START + r"eval\s+((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|\n'\"])*)")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash < file`, `sh -`, `bash -s`), --version and
# --help aside.
STDIN_SHELL = re.compile(START + SHELL_NAMES + r"(?!\s+(?:--version|--help|-h)(?:\s|$))(?:\s+" + SHELL_FLAG + r")*?"
                         r"(?:\s+-[A-Za-z]*s[A-Za-z]*(?=\s|$)|\s+-(?=\s|$)|\s*(?:$|[;&|)`\n<]))")
# find's actions run in a shell of their own: its arguments (quote- and escape-aware, an escaped newline included), only
# at a command position, the executable named by path or not.
FIND_ARGS = re.compile(START + r"(?:\S*/)?find\b((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|\\[\s\S]|[^;&|\n\\'\"])*)")
FIND_ACTION = re.compile(r"\s-(?:exec|execdir|ok|okdir)\s+([^\n]*?)(?:\s*\\;|\s+\+(?=\s|$)|\s+(?:';'|\";\"|'\+'|\"\+\")(?=\s|$))")
FIND_WRITES = re.compile(r"\s-(?:delete|fprint\w*|fls)\b")
ANSI_ESCAPE = re.compile(r"\$'[^']*\\")

PrefixInfo = namedtuple("PrefixInfo", "index env scrubbed env_split")


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


def mask_quotes(text):
    """text with each quoted string's contents blanked, keeping every offset: a separator or command word inside quotes
    is then not one, and a span found in the masked text slices the same bytes from the original."""
    return QUOTED.sub(lambda m: m.group(0)[0] + "_" * (len(m.group(0)) - 2) + m.group(0)[-1], text)


def join_continuations(text):
    """text with each backslash-newline removed, as the shell does outside single quotes."""
    out, i, n, single = [], 0, len(text), False
    while i < n:
        c = text[i]
        if single:
            single = c != "'"
            out.append(c)
            i += 1
        elif c == "'":
            single = True
            out.append(c)
            i += 1
        elif c == "\\" and text.startswith("\n", i + 1):
            i += 2
        elif c == "\\":
            out.append(text[i:i + 2])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def name_of(path):
    return path.rstrip("/").rsplit("/", 1)[-1]


def takes_value(wrapper, word):
    """Whether the flag word, in a wrapper's arguments, takes the next word as its value."""
    shorts, longs, _ = WRAPPER_FLAGS.get(wrapper, ("", (), None))
    if word.startswith("--"):
        return word[2:] in longs
    return bool(shorts) and re.fullmatch(rf"-{_letters_before(shorts)}[{shorts}]", word) is not None


def split_prefix(words):
    """A PrefixInfo for a command's words, past the prefix words, their flags and their operands: index (of the command
    word; past the end for a lookup like `command -v x`, which runs nothing), env (the VAR=value assignments that reach
    it), scrubbed (env -i or -u removed the inherited DRY_RUN) and env_split (env -S, which runs a string)."""
    env, wrapper, i, scrubbed, split = {}, None, 0, False, False
    while i < len(words):
        w = words[i]
        m = ASSIGN.match(w)
        base = name_of(w) if name_of(w) in COMMAND_WORDS else w
        if m:
            env[m.group(1)] = m.group(2)
        elif base in PREFIX_WORDS or base in WRAPPER_FLAGS:
            wrapper = base
        elif wrapper and w.startswith("-") and not w.startswith("--") and wrapper in LOOKUP_FLAGS and \
                re.fullmatch(rf"-[A-Za-z]*[{LOOKUP_FLAGS[wrapper]}][A-Za-z]*", w):
            return PrefixInfo(len(words), env, scrubbed, split)
        elif wrapper and w.startswith("-"):
            if wrapper == "env":
                value = words[i + 1] if i + 1 < len(words) else ""
                if w == "--split-string" or (not w.startswith("--") and "S" in w):
                    split = True
                if w in ("-", "--ignore-environment") or (not w.startswith("--") and re.fullmatch(r"-[A-Za-z]*i[A-Za-z]*", w)):
                    env.clear()
                    scrubbed = True
                name = value if w in ("-u", "--unset") else (w[2:] if w.startswith("-u") and not w.startswith("--") else
                                                             w.split("=", 1)[1] if w.startswith("--unset=") else None)
                if name == "DRY_RUN":
                    env.pop("DRY_RUN", None)
                    scrubbed = True
            i += 2 if takes_value(wrapper, w) else 1
            continue
        elif wrapper and WRAPPER_FLAGS.get(wrapper, (0, 0, None))[2] and re.fullmatch(WRAPPER_FLAGS[wrapper][2], w):
            pass
        else:
            break
        i += 1
    return PrefixInfo(i, env, scrubbed, split)


def env_split(command):
    """Whether command runs `env -S`/`--split-string` (within env's own options), which runs a string nothing here
    splits as env does."""
    return any(split_prefix(segment.split()).env_split for segment in SEPARATOR.split(bare(command)))


def substitutions(text, quotes=True):
    """The (body, offset) of each $(...) and `...` substitution the shell would run in text: outside single quotes (but
    inside double ones), with escapes honoured and parentheses balanced across nested quotes. In an unquoted heredoc
    body (quotes=False) a quote is just a character."""
    out, i, n, dq = [], 0, len(text), False
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif quotes and c == '"':
            dq, i = not dq, i + 1
        elif quotes and c == "'" and not dq:
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j, quote = 1, i + 2, None
            while j < n and depth:
                d = text[j]
                if d == "\\":
                    j += 1
                elif quote:
                    quote = None if d == quote else quote
                elif d in "'\"":
                    quote = d
                elif d == "(":
                    depth += 1
                elif d == ")":
                    depth -= 1
                j += 1
            out.append((text[i + 2:j - 1] if depth == 0 else text[i + 2:j], i))
            i = j
        elif c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append((text[i + 1:j], i))
            i = j + 1
        else:
            i += 1
    return out


def find_args(plain):
    """(original args, masked args, offset before them) for each find at a command position of plain."""
    masked = mask_quotes(plain)
    return [(plain[m.start(1):m.end(1)], masked[m.start(1):m.end(1)], m.start(1)) for m in FIND_ARGS.finditer(masked)]


def inner_strings(command):
    """(text, kind, before) for each string a shell would run that bare() sets aside. kind is "shell" (the argument of
    `sh -c`: its own command line, so the assignments before it count), "eval", "substitution" (only an earlier export
    reaches it), "find" (an action) or "opaque" (an ANSI-C string, which only a shell can decode). before is the
    command's text ahead of it."""
    plain = HEREDOC.sub(r"\1\4", command)
    masked = mask_quotes(plain)
    found = []
    for m in SHELL_C.finditer(masked):
        if SHELL_NO_EXEC.search(m.group("flags")):
            continue  # bash -n -c checks syntax and runs nothing; the outer shell's substitutions are scanned below
        arg = plain[m.start("arg"):m.end("arg")]
        try:
            words = shlex.split(arg.replace("$'", "'"))  # a $'...' string without an escape is the plain quoted one
        except ValueError:
            words = []
        found.append(("", "opaque", "") if ANSI_ESCAPE.search(arg) or len(words) != 1 else (words[0], "shell", plain[:m.start("arg")]))
    for m in EVAL_ARGS.finditer(masked):
        args = plain[m.start(1):m.end(1)]
        if ANSI_ESCAPE.search(args):
            found.append(("", "opaque", ""))
            continue
        try:
            words = shlex.split(args.replace("$'", "'"))
        except ValueError:
            words = [args.replace("'", "").replace('"', "")]
        if words[:1] == ["--"]:
            words = words[1:]
        found.append((" ".join(words), "eval", plain[:m.start(1)]))
    for original, _, at in find_args(plain):
        found += [(a.group(1), "find", plain[:at]) for a in FIND_ACTION.finditer(original)]
    for m in HEREDOC.finditer(command):
        if not m.group(2) and m.group("body"):  # an unquoted heredoc body expands; a quoted one is inert
            found += [(body, "substitution", command[:m.start()]) for body, _ in substitutions(m.group("body"), quotes=False)]
    found += [(body, "substitution", plain[:at]) for body, at in substitutions(plain)]
    return found


def find_writes(command):
    """The find actions that write whatever they run: -delete, -fprint and -fls, outside the -exec actions' own
    arguments (those commands are checked as commands)."""
    plain = HEREDOC.sub(r"\1\4", command)
    hits = []
    for original, masked, _ in find_args(plain):
        top = list(masked)
        for a in FIND_ACTION.finditer(original):
            top[a.start():a.end()] = " " * (a.end() - a.start())
        hits += [m.group(0).strip() for m in FIND_WRITES.finditer("".join(top))]
    return hits


class Timeout(BaseException):
    """Raised by the alarm: a command the guard could not analyse in time."""


def _alarm(signum, frame):
    raise Timeout()


def deadline(seconds=5):
    """Arm an alarm for the work after it (where the platform has SIGALRM), so a command that is slow to analyse is
    denied by the guard instead of timing the hook out, which lets the call through."""
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(seconds)
