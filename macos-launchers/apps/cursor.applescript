-- TEMPLATE: rendered by macos-launchers/Makefile install-% recipe.
-- Tokens: __SLUG__, __CURSOR_BIN__.
-- Do not invoke directly; use `make install` instead.
--
-- --extensions-dir keeps the profile's extensions apart from the personal
-- ~/.cursor/extensions; --user-data-dir alone does not move them.
-- CLAUDE_CONFIG_DIR gives the Claude Code extension and /ide lockfiles the
-- profile's ~/.claude-<slug>. The editor's processes inherit this launch env.

on run
	do shell script "CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" __CURSOR_BIN__ --user-data-dir=\"$HOME/.cursor-__SLUG__\" --extensions-dir=\"$HOME/.cursor-__SLUG__/extensions\" > /dev/null 2>&1 &"
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" __CURSOR_BIN__ --user-data-dir=\"$HOME/.cursor-__SLUG__\" --extensions-dir=\"$HOME/.cursor-__SLUG__/extensions\"" & pathArgs & " > /dev/null 2>&1 &"
end open
