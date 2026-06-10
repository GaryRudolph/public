# Submodule init fragment
#
# Include or merge into workspace Makefile `init` when `.gitmodules` is present.
# Runs before per-repo `make init`.

	@set -euo pipefail; \
	if [ -f .gitmodules ]; then \
	  printf '\033[1m==> git submodule update --init --recursive\033[0m\n'; \
	  git submodule update --init --recursive; \
	  echo ""; \
	fi
