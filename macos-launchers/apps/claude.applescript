-- TEMPLATE: rendered by macos-launchers/Makefile install-% recipe.
-- Tokens: __SLUG__.
-- Do not invoke directly; use `make install` instead.
--
-- --env CLAUDE_CONFIG_DIR points the desktop app's Code-tab sessions at the
-- profile's Claude Code config (~/.claude-<slug>), the same directory the
-- claude-<slug> shell function uses. The desktop app only honors this variable
-- from its own launch environment, never from the login shell. -n keeps it
-- applying when another Claude instance is already running.

on run
	do shell script "open -na Claude --env CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" --args --user-data-dir=\"$HOME/Library/Application Support/Claude-__SLUG__\""
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "open -na Claude --env CLAUDE_CONFIG_DIR=\"$HOME/.claude-__SLUG__\" --args --user-data-dir=\"$HOME/Library/Application Support/Claude-__SLUG__\"" & pathArgs
end open
