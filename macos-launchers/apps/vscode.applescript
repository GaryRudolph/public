-- TEMPLATE: rendered by macos-launchers/Makefile install recipe.
-- Tokens: __SLUG__, __CODE_BIN__.
-- Do not invoke directly; use `make install` instead.
--
-- --extensions-dir keeps the profile's extensions apart from the personal
-- ~/.vscode/extensions; --user-data-dir alone does not move them.
-- CLAUDE_CONFIG_DIR gives the Claude Code extension and /ide lockfiles the
-- profile's ~/.claude-<slug>. The editor's processes inherit this launch env.
--
-- __CODE_BIN__ is single-quoted because VS Code's bundled `code` script lives
-- at `/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code`
-- when not on PATH; the spaces would otherwise break shell parsing.

on run
	do shell script "CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" '__CODE_BIN__' --user-data-dir=\"$HOME/.vscode-__SLUG__\" --extensions-dir=\"$HOME/.vscode-__SLUG__/extensions\" > /dev/null 2>&1 &"
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" '__CODE_BIN__' --user-data-dir=\"$HOME/.vscode-__SLUG__\" --extensions-dir=\"$HOME/.vscode-__SLUG__/extensions\"" & pathArgs & " > /dev/null 2>&1 &"
end open
