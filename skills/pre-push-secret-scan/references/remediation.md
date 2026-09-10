# Remediating unpushed commits

Contents:
- [Before touching history](#before-touching-history)
- [If the value was ever pushed](#if-the-value-was-ever-pushed)
- [Recipe A: only the newest commit](#recipe-a-only-the-newest-commit)
- [Recipe B: strip a path from every unpushed commit](#recipe-b-strip-a-path-from-every-unpushed-commit)
- [Recipe C: redact content across unpushed commits](#recipe-c-redact-content-across-unpushed-commits)
- [Recipe D: rewrite a commit message](#recipe-d-rewrite-a-commit-message)
- [Verify](#verify)
- [Recovery](#recovery)

All recipes rewrite history and therefore need explicit developer approval first. They are safe
here only because every target commit is unpushed: nobody else has these SHAs.

## Before touching history

Run all of these and stop if any fails:

```bash
git status --short                      # working tree must be clean (stash otherwise)
git worktree list                       # other worktrees on this branch complicate rebases
git rev-list HEAD --not --remotes       # every target SHA must appear here
git branch backup/pre-secret-scan       # cheap undo point
```

Determine the base commit the rewrite starts from — the parent of the oldest unpushed commit:

```bash
BASE=$(git rev-list HEAD --not --remotes | tail -1)^
```

If the branch has no remote counterpart yet, `BASE` may not exist (the oldest unpushed commit is
the root commit). In that case use `--root` in place of `$BASE` for `git rebase`.

## If the value was ever pushed

Rewriting only helps for commits that exist nowhere else. Before rewriting, ask whether the value
itself is live:

- Already on a remote, or present in an open PR, CI log, or a colleague's clone → **rotate the
  credential first**; history rewriting alone does not undo the exposure, and force-pushing over a
  shared branch is a separate, disruptive decision for the developer to make.
- A real, currently valid credential that never left the machine → rewriting is enough, but
  recommend rotation anyway: the value has also passed through the editor, the shell history, and
  the reflog.
- An account ID, hostname, or path → rewriting is enough; nothing to rotate.

## Recipe A: only the newest commit

The common case, and the cheapest.

```bash
# Remove a file that should never have been tracked
git rm --cached path/to/.env
printf '.env\n' >> .gitignore
git add .gitignore
git commit --amend --no-edit

# Or: fix the content, then fold it into the same commit
git add src/config.py
git commit --amend --no-edit
```

`git rm --cached` keeps the file in the working tree — the developer's local `.env` is not
deleted.

## Recipe B: strip a path from every unpushed commit

Non-interactive, and verified to preserve the working-tree copies. List every offending path in a
single `git rm`:

```bash
printf '.env\nnode_modules/\ntmp/\n.aws/\n' >> .gitignore
git rebase "$BASE" --exec 'git rm -r --cached --ignore-unmatch -q .env node_modules .aws tmp && git commit --amend --no-edit --allow-empty -q'
git add .gitignore && git commit -m "chore: ignore local environment files"
```

`--ignore-unmatch` keeps the exec from failing on commits that never touched the path;
`--allow-empty` keeps the rebase from halting when a commit contained nothing else. To drop the
commits that ended up empty:

```bash
git rebase -f --no-keep-empty "$BASE"
```

## Recipe C: redact content across unpushed commits

Write an idempotent redaction script outside the repository (the scratchpad directory), then run it
once per commit. Idempotence matters: it runs against every commit, including ones where the value
is absent.

```python
# /path/to/scratchpad/redact.py
import pathlib
REPLACEMENTS = {
  '"ghp_REALTOKENVALUE"': 'os.environ["GH_TOKEN"]',
  '<the literal 12-digit account id>': '${AWS_ACCOUNT_ID}',
}
for path in ["src/config.py", "template.yaml"]:
  p = pathlib.Path(path)
  if not p.exists():
    continue
  text = original = p.read_text()
  for old, new in REPLACEMENTS.items():
    text = text.replace(old, new)
  if text != original:
    p.write_text(text)
```

```bash
git rebase "$BASE" --exec 'python3 /path/to/scratchpad/redact.py && git add -u && git commit --amend --no-edit --allow-empty -q'
```

Replacing a literal with an environment lookup changes runtime behaviour: the substitute must be
valid code, and the developer needs to know the value now has to come from somewhere else. Say so
when reporting the fix. If the replacement is not mechanical, do Recipe A per commit via
`git rebase --onto` or an interactive rebase instead of guessing.

## Recipe D: rewrite a commit message

For the newest commit:

```bash
git commit --amend -m "fix: point to the production endpoint"
```

For an older unpushed commit, drive the interactive rebase non-interactively (never launch
`git rebase -i` without both editors overridden — an editor prompt hangs the session):

```bash
printf 'fix: point to the production endpoint\n' > /path/to/scratchpad/newmsg.txt
GIT_SEQUENCE_EDITOR="sed -i.bak 's/^pick 682fce0/reword 682fce0/'" \
GIT_EDITOR="cp /path/to/scratchpad/newmsg.txt" \
git rebase -i "$BASE"
```

`GIT_EDITOR="cp <file>"` works because git appends the message file as the final argument.

## Verify

```bash
python3 scripts/scan_unpushed.py            # findings must be gone or explained
git log --oneline "$BASE"..HEAD             # commits still make sense
git range-diff "$BASE"..backup/pre-secret-scan "$BASE"..HEAD   # what the rewrite changed
git log -S'<the removed value>' --all       # value gone from every ref, including the backup
```

The last check matters: `backup/pre-secret-scan` still holds the secret. Delete it once the
developer confirms the result, and mention that the value also survives in the reflog until it
expires (`git reflog expire --expire=now --all && git gc --prune=now` clears it, only run on the
developer's explicit request).

Do not push. Report the result and let the developer push.

## Recovery

```bash
git rebase --abort                       # mid-rebase
git reset --hard backup/pre-secret-scan  # after a completed rewrite
git reflog                               # if the backup branch was not created
```
