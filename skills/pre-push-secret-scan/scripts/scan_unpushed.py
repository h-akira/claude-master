#!/usr/bin/env python3
"""Scan not-yet-pushed git commits for content that must not be published.

Reports path-based findings (files that should have been gitignored) and
content-based findings (credentials, account identifiers, private hosts) for
every commit that exists locally but on no remote.

Exit codes: 0 = no findings, 1 = findings reported, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from typing import Iterable, Iterator, Pattern

HIGH = "high"
MEDIUM = "medium"
LOW = "low"
SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}

DEFAULT_ALLOWLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allowlist.txt")

# Files whose content is skipped: machine-generated, huge, and hopeless to review.
SKIP_CONTENT_PATTERNS = [
  r"(?:^|/)(?:package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Cargo\.lock|Gemfile\.lock|composer\.lock|go\.sum)$",
  r"\.min\.(?:js|css)$",
  r"\.(?:map|lock)$",
  r"(?:^|/)(?:node_modules|vendor|dist|build)/",
]

LARGE_FILE_BYTES = 1_000_000
MAX_LINE_LENGTH = 4000
DEFAULT_PER_RULE_LIMIT = 20


@dataclass(frozen=True)
class PathRule:
  name: str
  severity: str
  pattern: str
  reason: str
  exceptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContentRule:
  name: str
  severity: str
  pattern: str
  reason: str
  group: int = 0          # capture group holding the interesting value
  mask: bool = False      # mask the value in the report (credential-like)
  flags: int = 0


PATH_RULES: list[PathRule] = [
  PathRule("dotenv", HIGH, r"(?:^|/)\.env(?:\.[^/]*)?$",
           "Environment file; usually holds credentials.",
           exceptions=(r"\.env\.(?:example|sample|template|dist|defaults)$",)),
  PathRule("aws-config-dir", HIGH, r"(?:^|/)\.aws/",
           "AWS CLI config/credentials directory."),
  PathRule("sam-build-dir", MEDIUM, r"(?:^|/)\.aws-sam/",
           "AWS SAM build output; contains packaged artifacts and account-specific metadata."),
  PathRule("credential-file", HIGH,
           r"(?:^|/)(?:credentials|\.netrc|\.npmrc|\.pypirc|\.git-credentials)$",
           "Credential store file."),
  PathRule("docker-config", HIGH, r"(?:^|/)\.docker/config\.json$",
           "Docker registry auth config."),
  PathRule("private-key", HIGH,
           r"(?:\.(?:pem|key|p8|p12|pfx|jks|keystore|ppk|asc)$|(?:^|/)id_(?:rsa|dsa|ecdsa|ed25519)$|(?:^|/)\.ssh/)",
           "Private key / certificate material.",
           exceptions=(r"\.pub$", r"(?:^|/)public[^/]*\.pem$")),
  PathRule("secrets-file", HIGH,
           r"(?:^|/)(?:secrets?|credentials?)[^/]*\.(?:json|ya?ml|toml|ini|cfg|txt)$",
           "File named like a secret store."),
  PathRule("terraform-state", HIGH, r"(?:\.tfstate(?:\.backup)?$|(?:^|/)\.terraform/)",
           "Terraform state contains resource identifiers and sometimes secrets."),
  PathRule("terraform-vars", MEDIUM, r"\.tfvars$",
           "Terraform variable file; often holds account-specific values.",
           exceptions=(r"\.example\.tfvars$", r"\.tfvars\.example$")),
  PathRule("serverless-dir", MEDIUM, r"(?:^|/)\.serverless/",
           "Serverless Framework build output."),
  PathRule("tmp-dir", MEDIUM, r"(?:^|/)(?:tmp|temp|\.tmp|\.cache)/",
           "Temporary directory; should not be tracked."),
  PathRule("node-modules", MEDIUM, r"(?:^|/)node_modules/",
           "Dependency directory; should be gitignored."),
  PathRule("python-artifact", MEDIUM,
           r"(?:(?:^|/)__pycache__/|\.py[co]$|(?:^|/)(?:env|venv|\.venv)/|\.egg-info/)",
           "Python virtualenv or build artifact."),
  PathRule("build-artifact", MEDIUM, r"(?:^|/)(?:dist|build|out|target|\.next|\.nuxt)/",
           "Build output directory."),
  PathRule("vendor-dir", MEDIUM, r"(?:^|/)vendor/",
           "Vendored dependency directory."),
  PathRule("database-dump", MEDIUM, r"\.(?:sqlite3?|db|mdb|dump|bak)$|\.sql\.(?:gz|zip)$",
           "Database file or dump; may contain production data."),
  PathRule("shell-history", HIGH, r"(?:^|/)\.(?:bash|zsh|sh|python)_history$",
           "Shell history; frequently contains pasted secrets."),
  PathRule("log-file", LOW, r"\.log$|(?:^|/)logs?/",
           "Log file; may contain identifiers or tokens."),
  PathRule("os-junk", LOW, r"(?:^|/)(?:\.DS_Store|Thumbs\.db|desktop\.ini)$",
           "OS metadata file."),
  PathRule("editor-local", LOW, r"(?:^|/)(?:\.idea|\.vscode)/",
           "Editor-local settings; may embed absolute local paths.",
           exceptions=(r"(?:^|/)\.vscode/(?:extensions|settings)\.json$",)),
]

CONTENT_RULES: list[ContentRule] = [
  ContentRule("aws-access-key-id", HIGH,
              r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b",
              "AWS access key ID.", mask=True),
  ContentRule("aws-secret-access-key", HIGH,
              r"(?i)aws[_-]?secret[_-]?access[_-]?key\W{0,10}([A-Za-z0-9/+=]{40})\b",
              "AWS secret access key.", group=1, mask=True),
  ContentRule("private-key-block", HIGH,
              r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----",
              "Embedded private key."),
  ContentRule("github-token", HIGH,
              r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b",
              "GitHub token.", mask=True),
  ContentRule("slack-token", HIGH, r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
              "Slack token.", mask=True),
  ContentRule("slack-webhook", HIGH, r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+",
              "Slack incoming webhook URL.", mask=True),
  ContentRule("google-api-key", HIGH, r"\bAIza[0-9A-Za-z_-]{35}\b",
              "Google API key.", mask=True),
  ContentRule("openai-anthropic-key", HIGH,
              r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}\b",
              "OpenAI / Anthropic style API key.", mask=True),
  ContentRule("stripe-key", HIGH, r"\b[srp]k_(?:live|test)_[A-Za-z0-9]{10,}\b",
              "Stripe API key.", mask=True),
  ContentRule("npm-token", HIGH, r"\bnpm_[A-Za-z0-9]{36}\b", "npm access token.", mask=True),
  ContentRule("pypi-token", HIGH, r"\bpypi-[A-Za-z0-9_-]{16,}\b", "PyPI API token.", mask=True),
  ContentRule("jwt", HIGH,
              r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
              "JSON Web Token.", mask=True),
  ContentRule("basic-auth-url", HIGH,
              r"\b[a-z][a-z0-9+.-]*://[^/\s:@\"']+:[^/\s:@\"']+@[^\s\"']+",
              "URL with embedded credentials.", mask=True),
  ContentRule("generic-secret-assignment", HIGH,
              r"(?i)(?:^|[^A-Za-z0-9])[A-Za-z0-9_]*(?:pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|"
              r"client[_-]?secret|auth[_-]?key|credential)\w*\s*[:=]\s*[\"']?([^\s\"',;)]{8,})",
              "Hard-coded secret assignment.", group=1, mask=True),
  ContentRule("aws-arn-account-id", HIGH,
              r"arn:aws[a-z-]*:[^:\s]*:[^:\s]*:(\d{12}):",
              "AWS account ID inside an ARN.", group=1),
  ContentRule("aws-account-id", HIGH, r"(?<![\d.])\d{12}(?![\d.])",
              "12-digit number; possibly an AWS account ID."),
  ContentRule("aws-resource-host", HIGH,
              r"\b[A-Za-z0-9][A-Za-z0-9._-]*\.(?:amazonaws\.com(?:\.cn)?|cloudfront\.net|"
              r"awsapps\.com|amplifyapp\.com|elasticbeanstalk\.com|awsstatic\.com)\b",
              "AWS-hosted endpoint; identifies deployed resources."),
  ContentRule("managed-host", MEDIUM,
              r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
              r"(?:com|net|org|io|jp|dev|app|co|ai|cloud|tech|xyz|work|team|online|store|shop)\b",
              "Hostname / domain; verify it is not a self-managed domain."),
  ContentRule("email-address", MEDIUM,
              r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b",
              "Email address."),
  ContentRule("global-ip", MEDIUM,
              r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])",
              "Globally routable IP address."),
  ContentRule("local-user-path", LOW,
              r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)([A-Za-z0-9._-]+)/?",
              "Absolute path containing a local account name.", group=1),
]


@dataclass
class Finding:
  severity: str
  rule: str
  reason: str
  commit: str
  subject: str
  path: str
  line: int | None
  value: str
  excerpt: str


@dataclass
class ScanResult:
  base: str
  commits: list[dict[str, str]] = field(default_factory=list)
  findings: list[Finding] = field(default_factory=list)
  notes: list[str] = field(default_factory=list)
  suppressed: dict[str, int] = field(default_factory=dict)


class Git:
  def __init__(self, repo: str) -> None:
    self.repo = repo

  def run(self, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
      ["git", "-c", "core.quotepath=false", "-C", self.repo, *args],
      capture_output=True, text=True, errors="replace",
    )
    if check and proc.returncode != 0:
      raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def load_allowlist(path: str) -> tuple[set[str], list[str]]:
  hosts: set[str] = set()
  placeholders: list[str] = []
  section = "hosts"
  if not os.path.exists(path):
    return hosts, placeholders
  with open(path, encoding="utf-8") as handle:
    for raw in handle:
      line = raw.strip()
      if not line or line.startswith("#"):
        continue
      if line.startswith("[") and line.endswith("]"):
        section = line[1:-1].strip().lower()
        continue
      if section == "hosts":
        hosts.add(line.lower())
      else:
        placeholders.append(line.lower())
  return hosts, placeholders


def host_allowed(host: str, hosts: set[str]) -> bool:
  host = host.lower().rstrip(".")
  if host in hosts:
    return True
  return any(host.endswith("." + entry) for entry in hosts)


def mask_value(value: str) -> str:
  if len(value) <= 8:
    return value[0] + "*" * (len(value) - 1)
  if len(value) <= 16:
    return value[:3] + "*" * 6 + value[-2:]
  return value[:4] + "*" * 6 + value[-6:]


def compile_rules() -> tuple[list[tuple[PathRule, Pattern[str], list[Pattern[str]]]],
                             list[tuple[ContentRule, Pattern[str]]]]:
  path_rules = [
    (rule, re.compile(rule.pattern), [re.compile(exc) for exc in rule.exceptions])
    for rule in PATH_RULES
  ]
  content_rules = [(rule, re.compile(rule.pattern, rule.flags)) for rule in CONTENT_RULES]
  return path_rules, content_rules


def resolve_commits(git: Git, base: str | None) -> tuple[str, list[dict[str, str]], list[str]]:
  notes: list[str] = []
  if base:
    rev_args = [f"{base}..HEAD"]
    label = f"{base}..HEAD"
  else:
    remotes = git.run("remote").split()
    if not remotes:
      notes.append("No git remote configured: every local commit is treated as unpushed.")
      rev_args = ["HEAD"]
      label = "HEAD (no remote)"
    else:
      rev_args = ["HEAD", "--not", "--remotes"]
      label = "HEAD --not --remotes"
  out = git.run("log", "--no-merges", "--date=short",
                "--format=%H%x1f%h%x1f%an%x1f%ad%x1f%s%x1f%b%x1e", *rev_args)
  commits: list[dict[str, str]] = []
  for record in out.split("\x1e"):
    record = record.strip("\n")
    if not record.strip():
      continue
    parts = record.split("\x1f")
    if len(parts) < 6:
      continue
    commits.append({
      "sha": parts[0], "short": parts[1], "author": parts[2],
      "date": parts[3], "subject": parts[4], "body": parts[5].strip(),
    })
  merges = git.run("rev-list", "--merges", *rev_args).split()
  if merges:
    notes.append(f"{len(merges)} merge commit(s) in range were not content-scanned.")
  return label, commits, notes


def iter_added_lines(patch: str) -> Iterator[tuple[str, int, str]]:
  """Yield (path, new_line_number, added_line_text) from a unified diff."""
  path = ""
  line_no = 0
  hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
  for line in patch.splitlines():
    if line.startswith("+++ "):
      target = line[4:].strip()
      path = "" if target == "/dev/null" else target[2:] if target.startswith("b/") else target
      continue
    if line.startswith("--- ") or line.startswith("diff --git "):
      continue
    match = hunk_re.match(line)
    if match:
      line_no = int(match.group(1))
      continue
    if line.startswith("+") and path:
      yield path, line_no, line[1:]
      line_no += 1
    elif line.startswith(" "):
      line_no += 1


def should_skip_content(path: str, skip_res: list[Pattern[str]]) -> bool:
  return any(rx.search(path) for rx in skip_res)


def scan_text(
  text: str,
  content_rules: list[tuple[ContentRule, Pattern[str]]],
  hosts: set[str],
  placeholders: list[str],
) -> Iterator[tuple[ContentRule, str]]:
  """Yield (rule, matched_value) for a single line of text."""
  if len(text) > MAX_LINE_LENGTH:
    text = text[:MAX_LINE_LENGTH]
  for rule, regex in content_rules:
    for match in regex.finditer(text):
      value = match.group(rule.group) if rule.group else match.group(0)
      if not value:
        continue
      if rule.name == "generic-secret-assignment":
        low = value.lower()
        if any(token in low for token in placeholders):
          continue
        if re.fullmatch(r"[\W_]+", value):
          continue
      if rule.name in ("managed-host", "email-address", "aws-resource-host"):
        host = value.split("@")[-1]
        if host_allowed(host, hosts):
          continue
      if rule.name == "global-ip":
        try:
          addr = ipaddress.ip_address(value)
        except ValueError:
          continue
        if not addr.is_global:
          continue
        octets = value.split(".")
        if octets[-1] == "0" and octets[-2] == "0":
          continue  # network address: almost always a version number
        prefix = text[:match.start()]
        if re.search(r"(?i)[a-z]/$|version\D{0,3}$", prefix):
          continue  # e.g. "Chrome/131.0.0.0"
      if rule.name == "local-user-path" and value.lower() in ("runner", "user", "root", "ubuntu"):
        continue
      yield rule, value


def build_excerpt(text: str, value: str, mask: bool) -> str:
  shown = mask_value(value) if mask else value
  line = text.replace(value, shown) if mask else text
  line = line.strip()
  if len(line) > 200:
    idx = line.find(shown)
    start = max(0, idx - 60)
    line = ("…" if start else "") + line[start:start + 200] + "…"
  return line


def scan(
  git: Git,
  base: str | None,
  extra_hosts: Iterable[str],
  allowlist_path: str,
  per_rule_limit: int,
) -> ScanResult:
  hosts, placeholders = load_allowlist(allowlist_path)
  hosts.update(h.lower() for h in extra_hosts)
  path_rules, content_rules = compile_rules()
  skip_res = [re.compile(p) for p in SKIP_CONTENT_PATTERNS]

  label, commits, notes = resolve_commits(git, base)
  result = ScanResult(base=label, commits=commits, notes=notes)
  counts: dict[str, int] = {}

  seen_values: set[tuple[str, str, int, str]] = set()
  seen_lines: set[tuple[str, str, str, int]] = set()

  def add(finding: Finding, collapse: bool = False) -> None:
    key = (finding.commit, finding.path, finding.line or 0, finding.value)
    if key in seen_values:
      return
    seen_values.add(key)
    if collapse:
      # One finding per rule per line: several hosts on one line share an excerpt.
      line_key = (finding.rule, finding.commit, finding.path, finding.line or 0)
      if line_key in seen_lines:
        return
      seen_lines.add(line_key)
    seen = counts.get(finding.rule, 0)
    counts[finding.rule] = seen + 1
    if seen < per_rule_limit:
      result.findings.append(finding)
    else:
      result.suppressed[finding.rule] = counts[finding.rule] - per_rule_limit

  for commit in commits:
    sha, short, subject = commit["sha"], commit["short"], commit["subject"]

    # 1. commit message
    message = f"{subject}\n{commit['body']}"
    for line in message.splitlines():
      for rule, value in scan_text(line, content_rules, hosts, placeholders):
        add(Finding(rule.severity, rule.name, rule.reason, short, subject,
                    "<commit message>", None, value,
                    build_excerpt(line, value, rule.mask)), collapse=not rule.mask)

    # 2. touched paths
    name_status = git.run("diff-tree", "--no-commit-id", "-r", "--name-status", "--root", sha)
    added_paths: list[str] = []
    for row in name_status.splitlines():
      parts = row.split("\t")
      if len(parts) < 2:
        continue
      status, path = parts[0], parts[-1]
      if status.startswith("D"):
        continue
      if status.startswith("A"):
        added_paths.append(path)
      for rule, regex, exceptions in path_rules:
        if not regex.search(path):
          continue
        if any(exc.search(path) for exc in exceptions):
          continue
        add(Finding(rule.severity, f"path:{rule.name}", rule.reason, short, subject,
                    path, None, path, f"{status}\t{path}"))

    # 3. oversized additions
    for path in added_paths[:200]:
      try:
        size = int(git.run("cat-file", "-s", f"{sha}:{path}").strip())
      except (RuntimeError, ValueError):
        continue
      if size >= LARGE_FILE_BYTES:
        add(Finding(MEDIUM, "path:large-file",
                    "Large file added; check whether it is a build artifact or data dump.",
                    short, subject, path, None, str(size), f"{size / 1_048_576:.1f} MiB"))

    # 4. added content
    patch = git.run("diff-tree", "--no-commit-id", "-r", "-p", "--unified=0",
                    "--no-color", "--root", sha)
    for path, line_no, text in iter_added_lines(patch):
      if should_skip_content(path, skip_res):
        continue
      for rule, value in scan_text(text, content_rules, hosts, placeholders):
        add(Finding(rule.severity, rule.name, rule.reason, short, subject,
                    path, line_no, value, build_excerpt(text, value, rule.mask)),
            collapse=not rule.mask)

  if result.findings and not os.path.exists(os.path.join(git.repo, ".gitignore")):
    result.notes.append("Repository root has no .gitignore.")
  return result


def render(result: ScanResult) -> str:
  lines: list[str] = []
  lines.append(f"range   : {result.base}")
  lines.append(f"commits : {len(result.commits)} unpushed commit(s)")
  for commit in result.commits:
    lines.append(f"  {commit['short']}  {commit['date']}  {commit['subject']}")
  for note in result.notes:
    lines.append(f"note    : {note}")
  lines.append("")

  if not result.findings:
    lines.append("No findings. Nothing suspicious detected in the unpushed commits.")
    return "\n".join(lines)

  ordered = sorted(
    result.findings,
    key=lambda f: (SEVERITY_ORDER[f.severity], f.rule, f.commit, f.path, f.line or 0),
  )
  by_severity: dict[str, list[Finding]] = {}
  for finding in ordered:
    by_severity.setdefault(finding.severity, []).append(finding)

  summary = ", ".join(f"{sev}={len(items)}" for sev, items in by_severity.items())
  lines.append(f"findings: {len(result.findings)} ({summary})")
  lines.append("")

  for severity in (HIGH, MEDIUM, LOW):
    items = by_severity.get(severity)
    if not items:
      continue
    lines.append(f"=== {severity.upper()} ===")
    current_rule = ""
    for finding in items:
      if finding.rule != current_rule:
        current_rule = finding.rule
        lines.append(f"[{finding.rule}] {finding.reason}")
      where = f"{finding.path}:{finding.line}" if finding.line else finding.path
      lines.append(f"  {finding.commit}  {where}")
      lines.append(f"      {finding.excerpt}")
    lines.append("")

  if result.suppressed:
    for rule, extra in sorted(result.suppressed.items()):
      lines.append(f"note    : {extra} further [{rule}] match(es) not shown.")
  return "\n".join(lines)


def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--repo", default=".", help="repository path (default: cwd)")
  parser.add_argument("--base", help="explicit base revision; default is 'not on any remote'")
  parser.add_argument("--allow", action="append", default=[],
                      help="extra host suffix to ignore (repeatable, this run only)")
  parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="path to allowlist file")
  parser.add_argument("--limit", type=int, default=DEFAULT_PER_RULE_LIMIT,
                      help=f"max findings shown per rule (default: {DEFAULT_PER_RULE_LIMIT})")
  parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
  args = parser.parse_args(argv)

  try:
    repo_root = subprocess.run(
      ["git", "-C", args.repo, "rev-parse", "--show-toplevel"],
      capture_output=True, text=True,
    )
    if repo_root.returncode != 0:
      print(f"error: not a git repository: {args.repo}", file=sys.stderr)
      return 2
    git = Git(repo_root.stdout.strip())
    result = scan(git, args.base, args.allow, args.allowlist, args.limit)
  except RuntimeError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return 2

  if args.json:
    payload = {
      "base": result.base,
      "commits": result.commits,
      "notes": result.notes,
      "suppressed": result.suppressed,
      "findings": [asdict(f) for f in result.findings],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
  else:
    print(render(result))
  return 1 if result.findings else 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
