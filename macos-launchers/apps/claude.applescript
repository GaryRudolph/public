-- TEMPLATE: rendered by macos-launchers/Makefile install-% recipe.
-- Tokens: __SLUG__.
-- Do not invoke directly; use `make install` instead.

on run
	do shell script "open -na Claude --args --user-data-dir=\"$HOME/Library/Application Support/Claude-__SLUG__\""
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "open -na Claude --args --user-data-dir=\"$HOME/Library/Application Support/Claude-__SLUG__\"" & pathArgs
end open
