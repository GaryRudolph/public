# Definitions shared by every render of the canonical allowlist file
# (agents/allowlists/<org>.json; agents/allowlists/README.md has the format).
# Definitions only: callers prepend this text to their own jq program, so
# lib/allowlists.sh (the local installer) and agents/org/render.sh (Claude
# Code managed settings) render Claude Code rules from one definition.

# Stop on anything outside the format, so a typo in a key can't silently
# drop a list: the keys and lists the README names, each list an array of
# non-empty strings.
def meta_check:
    def fail(msg): error("allowlist format: " + msg);
    if type != "object" then fail("the top level must be an object") else . end
    | (keys - ["mcp", "read", "shell", "webfetch", "write"]) as $extra
    | if ($extra | length) > 0 then fail("unknown key " + ($extra | join(", "))) else . end
    | to_entries[] as {key: $k, value: $v}
    | (if $k == "read" or $k == "write" then ["deny"] else ["allow", "deny"] end) as $lists
    | if ($v | type) != "object" then fail($k + " must be an object")
      elif (($v | keys) - $lists | length) > 0
      then fail($k + " may only hold " + ($lists | join(" and ")) + ", not " + (($v | keys) - $lists | join(", ")))
      else . end
    | $v | to_entries[] as {key: $l, value: $a}
    | if ($a | type) != "array" then fail($k + "." + $l + " must be an array")
      elif any($a[]; type != "string" or test("^\\s*$")) then fail($k + "." + $l + " must hold non-empty strings")
      else . end
    | empty;

# Every shell entry is trimmed and, unless it quotes, its runs of whitespace
# collapsed before any target renders it, so " sudo" or "git  push" can't
# render a rule that matches nothing; an empty entry stops the render.
def shell_norm:
    gsub("^\\s+|\\s+$"; "")
    | if test("[\"']") then . else gsub("\\s+"; " ") end
    | if . == "" then error("empty shell entry") else . end;

# Claude Code. server:tool -> mcp__server__tool, server:* -> mcp__server__*.
# Split at the first colon (the tool part is the rest). An entry with no
# colon, no server or no tool stops the render rather than produce a rule
# such as mcp____tool.
def claude_mcp:
    if test("^[^:]+:.+$")
    then index(":") as $i | "mcp__" + .[:$i] + "__" + .[$i+1:]
    else error("bad mcp entry: " + .)
    end;

# A shell allow is the exact command, Bash(<entry>): a prefix would also
# approve the flags that run programs or write files (git fetch
# --upload-pack=, rg --pre, sort -o). An allow holding * gets no rule. A
# shell deny is the prefix, Bash(<entry>:*), or as written when it holds *.
def claude_allow: if test("[*]") then empty else "Bash(" + . + ")" end;
def claude_deny: if test("[*]") then "Bash(" + . + ")" else "Bash(" + . + ":*)" end;

# Gemini. A shell allow is a commandRegex matching the exact command: Gemini
# searches `\x00"command":"(?:<re>)` in the JSON of the tool's args, so the
# entry goes in JSON-escaped (as it appears there), then RE2-escaped, and a
# closing `"` pins the end. Every `"` inside the value is escaped as `\"`,
# so the bare one can only be the closing quote.
def gemini_allow_regex:
    tojson[1:-1]
    | gsub("(?<c>[\\\\.+*?()|\\[\\]{}^$])"; "\\\(.c)")
    | . + "\"";

# The permissions object Claude Code reads, from the canonical file.
def claude_permissions:
    {
        permissions: {
            allow: (
                (((.shell.allow    // []) | map(shell_norm | claude_allow)) +
                 ((.mcp.allow      // []) | map(claude_mcp)) +
                 ((.webfetch.allow // []) | map("WebFetch(domain:" + . + ")"))
                ) | unique
            ),
            deny: (
                (((.shell.deny    // []) | map(shell_norm | claude_deny)) +
                 ((.mcp.deny      // []) | map(claude_mcp)) +
                 ((.webfetch.deny // []) | map("WebFetch(domain:" + . + ")")) +
                 ((.read.deny     // []) | map("Read(" + . + ")")) +
                 ((.write.deny    // []) | map("Edit(" + . + ")"))
                ) | unique
            )
        }
    };
