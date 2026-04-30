-- TEMPLATE: rendered by macos-launchers/Makefile install recipe.
-- Tokens: __SLUG__, __CODE_BIN__.
-- Do not invoke directly; use `make install` instead.
--
-- __CODE_BIN__ is single-quoted because VS Code's bundled `code` script lives
-- at `/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code`
-- when not on PATH; the spaces would otherwise break shell parsing.

on run
	do shell script "'__CODE_BIN__' --user-data-dir=\"$HOME/.vscode-__SLUG__\" > /dev/null 2>&1 &"
end run

on open theItems
	set pathArgs to ""
	repeat with f in theItems
		set pathArgs to pathArgs & " " & quoted form of (POSIX path of f)
	end repeat
	do shell script "'__CODE_BIN__' --user-data-dir=\"$HOME/.vscode-__SLUG__\"" & pathArgs & " > /dev/null 2>&1 &"
end open
