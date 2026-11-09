# secrets.mk: single-repo secrets targets, per the personal secrets standard
# (standards/secrets/single-repo.md and makefile.md "Single-repo targets").
#
# In the repo's Makefile, after `SHELL := bash` and the help target:
#   include secrets.mk
# The repo's doctor target should depend on secrets-doctor, and its
# pre-commit hook and CI should run `make secrets-check` (CI adds ONLINE=1).
#
# FILE is a path under secrets/ without .sops: FILE=prod/api.env.

SECRETS_SCRIPT ?= scripts/secrets.sh
SECRETS_TOOLS  ?= sops age age-keygen gh

secrets_confirm = @if [ -z "$($(1))" ]; then \
  printf 'Refusing to run "make %s": %s\nRe-run with %s=1.\n' "$@" "$(2)" "$(1)"; \
  exit 1; \
fi

.PHONY: secrets-env secrets-encrypt secrets-decrypt secrets-check secrets-clean \
        secrets-updatekeys secrets-doctor secrets-mint secrets-sync

##@ Secrets

secrets-env: ## Dotenv, or one value with KEY=, to stdout; nothing on disk [FILE= KEY= FORMAT=dotenv]
	@FORMAT="$(FORMAT)" bash $(SECRETS_SCRIPT) env "$(FILE)" "$(KEY)"

secrets-encrypt: ## Encrypt cleartext to *.sops and delete the cleartext [FILE=, default all]
	@bash $(SECRETS_SCRIPT) encrypt $(FILE)

secrets-decrypt: ## Write cleartext beside *.sops, mode 0600; asks for a .env [FILE= CONFIRM=1]
	@CONFIRM="$(CONFIRM)" bash $(SECRETS_SCRIPT) decrypt $(FILE)

secrets-check: ## Keyless checks: ciphertext only, recipients, naming, environments [ONLINE=1]
	@bash $(SECRETS_SCRIPT) check $(if $(ONLINE),--online)

secrets-clean: ## Delete cleartext that has a *.sops sibling, then run secrets-check
	@bash $(SECRETS_SCRIPT) clean

secrets-updatekeys: ## Re-wrap files after a recipient change; ROTATE=1 makes a new data key [SCOPE=]
	@ROTATE="$(ROTATE)" bash $(SECRETS_SCRIPT) updatekeys $(SCOPE)

secrets-doctor: ## Check secrets tools and that an age identity is found (read-only)
	@missing=0; for t in $(SECRETS_TOOLS); do \
	  if command -v $$t >/dev/null 2>&1; then printf '  ok       %s\n' "$$t"; \
	  else printf '  missing  %s\n' "$$t"; missing=1; fi; \
	done; \
	if [ -n "$${SOPS_AGE_KEY:-}" ]; then echo "  ok       age identity: SOPS_AGE_KEY"; \
	elif [ -n "$${SOPS_AGE_KEY_FILE:-}" ] && [ -f "$${SOPS_AGE_KEY_FILE}" ]; then echo "  ok       age identity: SOPS_AGE_KEY_FILE"; \
	elif [ -f "$${XDG_CONFIG_HOME:-$$HOME/.config}/sops/age/keys.txt" ]; then echo "  ok       age identity: ~/.config/sops/age/keys.txt"; \
	else echo "  missing  age identity (age-keygen -o ~/.config/sops/age/keys.txt)"; missing=1; fi; \
	exit $$missing

##@ Danger

secrets-mint: ## New CI key for CONTEXT=actions|env-<env>|...: private half to GitHub (CONFIRM_MINT=1)
	$(call secrets_confirm,CONFIRM_MINT,it writes SOPS_AGE_KEY to GitHub)
	@bash $(SECRETS_SCRIPT) mint "$(CONTEXT)"

secrets-sync: ## Write <env>/<service>.env to Secret Manager; prints bindings [ENVIRONMENT= SERVICE=] (CONFIRM_SYNC=1)
	$(call secrets_confirm,CONFIRM_SYNC,it writes secret versions to the cloud)
	@bash $(SECRETS_SCRIPT) sync "$(ENVIRONMENT)" "$(SERVICE)"
