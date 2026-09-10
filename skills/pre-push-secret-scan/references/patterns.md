# Detection rules and triage guidance

Contents:
- [Two-stage design](#two-stage-design)
- [Path rules](#path-rules)
- [Content rules](#content-rules)
- [Triage guidance](#triage-guidance)
- [Blind spots](#blind-spots)
- [Tuning the allowlist](#tuning-the-allowlist)

## Two-stage design

`scripts/scan_unpushed.py` is deliberately over-sensitive: it finds *candidates* by regex and
never decides. Deciding is the second stage, done by reading the findings in context. A regex
cannot tell `example.com` in a docs snippet from a production hostname, so the script reports both
and the triage step separates them.

Consequence: never treat a clean scan as proof of safety, and never treat a finding as proof of a
leak.

## Path rules

Reported as `path:<name>`. Triggered by the path of any file added or modified by a commit.

| Rule | Severity | What it catches |
| --- | --- | --- |
| `dotenv` | high | `.env`, `.env.production` (`.env.example` / `.sample` / `.template` / `.dist` are exempt) |
| `aws-config-dir` | high | anything under `.aws/` |
| `credential-file` | high | `credentials`, `.netrc`, `.npmrc`, `.pypirc`, `.git-credentials` |
| `docker-config` | high | `.docker/config.json` |
| `private-key` | high | `*.pem`, `*.key`, `*.p8/p12/pfx/jks`, `id_rsa`, anything under `.ssh/` (`*.pub` exempt) |
| `secrets-file` | high | `secrets.yaml`, `credential.json`, and similar names |
| `terraform-state` | high | `*.tfstate`, `.terraform/` |
| `shell-history` | high | `.bash_history`, `.zsh_history` |
| `sam-build-dir` | medium | `.aws-sam/` |
| `terraform-vars` | medium | `*.tfvars` (`*.example.tfvars`, `*.tfvars.example` exempt) |
| `serverless-dir` | medium | `.serverless/` |
| `tmp-dir` | medium | `tmp/`, `temp/`, `.tmp/`, `.cache/` |
| `node-modules` | medium | `node_modules/` |
| `python-artifact` | medium | `__pycache__/`, `*.pyc`, `env/`, `venv/`, `.venv/`, `*.egg-info/` |
| `build-artifact` | medium | `dist/`, `build/`, `out/`, `target/`, `.next/`, `.nuxt/` |
| `vendor-dir` | medium | `vendor/` |
| `database-dump` | medium | `*.sqlite`, `*.db`, `*.dump`, `*.sql.gz` |
| `large-file` | medium | any added file >= 1 MiB |
| `log-file` | low | `*.log`, `logs/` |
| `os-junk` | low | `.DS_Store`, `Thumbs.db` |
| `editor-local` | low | `.idea/`, `.vscode/` (`settings.json`, `extensions.json` exempt) |

A `path:` finding almost always means a missing `.gitignore` entry. Fix both: strip the file from
history *and* add the pattern to `.gitignore`, otherwise it comes back on the next commit.

## Content rules

Applied to added (`+`) diff lines and to commit messages. Values of credential-like rules are
masked in the report (`AKIA******XAMPLE`); identifier-like rules print the value because judging
it requires seeing it.

| Rule | Severity | What it catches |
| --- | --- | --- |
| `aws-access-key-id` | high | `AKIA…`/`ASIA…`/`ABIA…`/`ACCA…` + 16 chars |
| `aws-secret-access-key` | high | 40-char value next to an `aws_secret_access_key` label |
| `private-key-block` | high | `-----BEGIN … PRIVATE KEY-----` |
| `github-token` | high | `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`/`github_pat_` |
| `slack-token`, `slack-webhook` | high | `xoxb-…`, `https://hooks.slack.com/services/…` |
| `google-api-key` | high | `AIza…` |
| `openai-anthropic-key` | high | `sk-`, `sk-ant-`, `sk-proj-` |
| `stripe-key`, `npm-token`, `pypi-token` | high | vendor-prefixed tokens |
| `jwt` | high | `eyJ….eyJ….…` |
| `basic-auth-url` | high | a URL carrying `user:password` in its authority part |
| `generic-secret-assignment` | high | `password`/`secret`/`token`/`api_key`/`client_secret` = literal (>= 8 chars) |
| `aws-arn-account-id` | high | 12-digit account ID inside an ARN |
| `aws-account-id` | high | any bare 12-digit run (bucket names often embed one) |
| `aws-resource-host` | high | `*.amazonaws.com`, `*.cloudfront.net`, `*.awsapps.com`, `*.amplifyapp.com`, `*.elasticbeanstalk.com` |
| `managed-host` | medium | any hostname on a common TLD that is not allowlisted |
| `email-address` | medium | email addresses on non-allowlisted domains |
| `global-ip` | medium | globally routable IPv4 (private, loopback, and version-number shapes filtered out) |
| `local-user-path` | low | `/Users/<name>/…`, `/home/<name>/…` |

Suppressed automatically: values containing a placeholder token from `[placeholders]` in
`allowlist.txt` (`example`, `dummy`, `your-`, `os.environ`, `process.env`, `${`, …), hosts under
`[hosts]`, private/loopback IPs, and duplicate matches of the same value at the same location.

Content scanning is skipped entirely for lockfiles, `*.min.js`, `*.map`, and paths inside
`node_modules/`, `vendor/`, `dist/`, `build/` — but the *path* rules still fire for those.

## Triage guidance

Work rule by rule and decide leak / not-leak with the surrounding code in view. Use
`git show <sha> -- <path>` when the one-line excerpt is not enough.

- **Vendor-prefixed tokens, key blocks, ARNs**: essentially always real. Escalate, and treat the
  credential as compromised if it is live (see `remediation.md`).
- **`generic-secret-assignment`**: a real secret when the value is high-entropy or looks
  human-chosen (`S3cretPassw0rd!`). Not a leak when it reads from the environment, references a
  secret manager, or is an obvious sample. Test fixtures with fake passwords are usually fine but
  say so explicitly rather than assuming.
- **`aws-account-id`**: 12-digit runs are also order numbers, epoch-ish IDs, and phone numbers.
  Check whether the surrounding text is AWS-related (`arn:`, `ecr`, `iam`, bucket, registry URL).
- **`aws-resource-host` / `managed-host`**: the decision is *"is this host operated by the
  author?"*. API Gateway IDs, CloudFront distributions, and custom domains in config files are
  leaks. Third-party service hosts appearing in dependency documentation are not. When the same
  domain appears repeatedly across the diff, report it once with a count rather than line by line.
- **`email-address`**: personal or corporate addresses in code and configs are leaks. The author's
  own commit-author address is not scanned (it is already in the pushed history).
- **`global-ip`**: bastion / server addresses are leaks; public DNS resolver addresses and
  documentation ranges usually are not.
- **`local-user-path`**: low value on its own, but it reveals the developer's account name and
  local directory layout. Worth mentioning, rarely worth rewriting history for.

## Blind spots

The script cannot see these. Skim the diff yourself when the change is small enough, and say so
when it is not:

- Secrets with no recognizable prefix or label (a bare 32-char hex string in a config value).
- Secrets that are base64/URL encoded, split across lines, or built by concatenation.
- Sensitive prose: internal project code names, customer names, unannounced product plans,
  personal data in fixtures or screenshots.
- Binary content: images, PDFs, `.zip`, database files. Only their paths and sizes are checked.
- Merge commits are not content-scanned (the report says so when the range contains any).
- Files removed by a later commit are still scanned, because they remain in the history that would
  be pushed — this is intentional, not a false positive.

## Scanning this skill itself

A commit that adds or edits this skill trips its own rules: the tables below name `amazonaws.com`
and friends, and `remediation.md` contains example patterns. Those hits are expected. Confirm the
path is inside the skill directory, then dismiss them.

## Tuning the allowlist

`scripts/allowlist.txt` ships with this skill and **is published with the repository**. Never add a
self-managed, customer, or internal domain to it — that would leak exactly what the skill exists to
protect.

For a one-off scan, pass hosts on the command line instead:

```bash
python3 scripts/scan_unpushed.py --allow cdn.thirdparty.example --allow docs.vendor.example
```

For a repository-local list, keep it outside the skill (for example `.git/scan-allowlist.txt`,
which is never committed) and point at it with `--allowlist`. Note that `--allowlist` replaces the
bundled file rather than extending it, so copy the defaults in first.
