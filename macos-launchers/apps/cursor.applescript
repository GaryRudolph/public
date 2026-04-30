-- TEMPLATE: rendered by macos-launchers/Makefile install-% recipe.
-- Tokens: __SLUG__, __CURSOR_BIN__.
-- Do not invoke directly; use `make install` instead.

on run
	do shell script "__CURSOR_BIN__ --user-data-dir=\"$HOME/.cursor-__SLUG__\" > /dev/null 2>&1 &"
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "__CURSOR_BIN__ --user-data-dir=\"$HOME/.cursor-__SLUG__\"" & pathArgs & " > /dev/null 2>&1 &"
end open
