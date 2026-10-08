# Changelog fragments

Don't add entries to `CHANGELOG.md` in a PR. Add your entry here as its own
file, and the release step folds every file into the new release section,
in merge order, and deletes them. Separate files mean PRs never conflict
over the changelog, in a merge queue or out of it. To fix an entry that
already shipped, edit `CHANGELOG.md` directly.

Name the file anything unique, ending in `.txt`: the branch slug
(`serve-grayscale-theme.txt`) or the PR number (`123.txt`). Write one fenced
block per entry:

````text
```release-note:fixed
`--serve` accepts `--theme grayscale`.
```
````

The kind after `release-note:` is a Keep a Changelog section: `added`,
`changed`, `deprecated`, `removed`, `fixed`, or `security`. One file can hold
several blocks of different kinds. Write the entry as it should read in the
changelog; the release step adds the leading `- `.

A PR with no user-visible change needs no fragment: label it `no-changelog`.
`python3 scripts/changelog.py check` validates the files, and
`python3 scripts/changelog.py preview` shows the next release's section.

This README keeps the directory in git between releases; leave it in place.
