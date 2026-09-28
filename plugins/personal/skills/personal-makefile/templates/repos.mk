# =============================================================================
# repos.mk — {{ESTATE_TITLE}} repository manifest
#
# Source of truth for the estate: every repository, its remote, default branch,
# and participation flags. Include from the root Makefile with `include repos.mk`.
#
# Variable name convention: REPO_URL.<dirname> / REPO_BRANCH.<dirname>
# =============================================================================

REPOS := {{REPOS_SPACE_SEPARATED}}

# Remote origin URLs — one REPO_URL.<dir> per repo
{{REPO_URL_BLOCK}}

# Default branches
{{REPO_BRANCH_BLOCK}}

REPOS_MAKE_INIT := {{REPOS_MAKE_INIT}}
REPOS_BUILD_ORDER := {{REPOS_BUILD_ORDER}}
REPOS_MAKE_CI := {{REPOS_MAKE_CI}}
REPOS_MAKE_CLEAN := {{REPOS_MAKE_CLEAN}}
REPOS_FOLLOW_ONLY := {{REPOS_FOLLOW_ONLY}}
REPOS_GH := $(filter-out $(REPOS_FOLLOW_ONLY),$(REPOS))
