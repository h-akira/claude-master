---
name: pre-push-secret-scan
description: >
  Audit not-yet-pushed git commits for content that must not be published, then report it to the
  developer and fix it on request. Detects credentials and tokens, AWS account IDs and resource
  endpoints, self-managed domains, emails and IPs, plus files that should have been gitignored
  (.env, tmp/, node_modules/, .aws/, .aws-sam/, keys, build artifacts). Use before running
  git push, when asked to review commits for leaked or private information, when asked whether it
  is safe to publish or open-source a branch, and for Japanese requests such as
  「push前に確認して」「機密情報が混ざっていないか調べて」「公開して大丈夫か見て」.
---

# Pre-push secret scan

## Overview

Commits that are already on a remote are out of scope — they are public already, and only
credential rotation helps there. This skill covers exactly the commits that exist locally and on no
remote, i.e. what the next `git push` would publish.

Two stages: `scripts/scan_unpushed.py` narrows the diff down to candidates by regex, then you judge
each candidate in context. The script never decides, and a clean scan is not proof of safety.

## Workflow

### 1. Scan

```bash
cd <repo root>
python3 <skill dir>/scripts/scan_unpushed.py
```

Default range is `HEAD --not --remotes` (everything on no remote). Useful flags:
`--repo <path>`, `--base <rev>` to force a range, `--json` for structured output,
`--allow <host>` to ignore an extra host for this run, `--limit N` per-rule cap (default 20).
Exit codes: `0` no findings, `1` findings, `2` error.

If the report says no remote is configured, every commit is in range — mention that, because the
result will be large and mostly historical.

### 2. Triage

Read `references/patterns.md` for what each rule means and how to separate real leaks from noise.
Open the real diff (`git show <sha> -- <path>`) whenever a one-line excerpt is not enough to
decide.

Then look for what the regexes cannot catch — unlabeled high-entropy strings, encoded values,
internal names, personal data, binary files. Review the diff directly when it is small enough; when
it is too large, say which parts you did not review.

Group the results before reporting: one entry per distinct issue, not per matched line. Ten
occurrences of the same domain are one finding with a count.

### 3. Report

Report in the language the developer is using. Structure:

1. **Range**: how many unpushed commits, which ones.
2. **Must fix**: real credentials, account IDs, private hosts, files that should be gitignored.
   For each: what it is, where (`<short sha> <path>:<line>`), and why it matters.
3. **Check please**: candidates whose status depends on intent — sample values, third-party
   domains, test fixtures.
4. **Not reviewed**: binaries, merge commits, anything skipped.
5. **Recommendation**: fix, or safe to push.

Keep credential values masked as the script masks them. Print identifiers (account IDs, hostnames)
in full — the developer cannot judge them otherwise.

Then stop and ask. Do not rewrite anything and do not push.

### 4. Act on the answer

- **"That's intentional"** → accept it, note it in the summary, move on. Do not argue and do not
  re-flag it in the same session. Nothing is recorded to disk, so it will surface again on the next
  scan; mention that once.
- **"Fix it"** → follow `references/remediation.md`. It has verified non-interactive recipes for
  amending the newest commit, stripping a path from every unpushed commit, redacting content across
  a rebase, and rewriting a commit message, plus the pre-flight checks and the backup branch.
  Show the exact commands and get approval before running the first history-rewriting one.
- **After fixing** → re-run the scanner, report what changed, and leave the push to the developer.

## Constraints

- Never run `git push`, and never force-push.
- Never rewrite a commit that appears on a remote. If a secret is already pushed, the answer is
  credential rotation, not a rebase.
- Always create the backup branch before rewriting, and always confirm the plan first.
- Never write a real secret, hostname, or account ID into a file inside this skill.
  `scripts/allowlist.txt` is published with the repository; it holds only well-known public hosts.
  Use `--allow` for one-off exceptions instead.
- Treat a finding as unresolved until the developer says otherwise. Reporting it is not fixing it.
