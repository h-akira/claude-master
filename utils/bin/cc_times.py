#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Created: 2026-10-03

import os
import re
import sys
import json
import glob
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
RECORD_TYPES = ("user", "assistant", "progress")
TAG_RE = re.compile(r"^\s*<[a-zA-Z][\w-]*>")
COMMAND_NAME_RE = re.compile(r"<command-name>\s*(.*?)\s*</command-name>", re.S)
COMMAND_ARGS_RE = re.compile(r"<command-args>\s*(.*?)\s*</command-args>", re.S)
# Commands that never carry a meaningful prompt
SKIP_COMMANDS = {"/clear"}


@dataclass
class Session:
  session_id: str
  start: datetime
  latest: datetime
  turns: int
  working: timedelta
  first_prompt: str


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="""\
ClaudeCodeの会話履歴（~/.claude/projects/配下の セッションID.jsonl）から、
セッションごとのAIの稼働時間を計算して表示する。

稼働時間は「ユーザー入力の時刻から、次のユーザー入力の直前の最終レコードの時刻まで」をターンとし、その合計とする。
ユーザーが考えている待ち時間は含まないが、権限確認などの待ち時間は含まれる。
""", formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--version", action="version", version="%(prog)s 0.0.1")
  group = parser.add_mutually_exclusive_group()
  group.add_argument("-c", "--cwd", metavar="dir", default=".",
                     help="対象のディレクトリ（省略時はカレントディレクトリ）。履歴の保存先はこのパスから決まる")
  group.add_argument("-d", "--direct", metavar="projects-dir",
                     help="~/.claude/projects/配下の履歴ディレクトリを直接指定する（ディレクトリ名を変えた場合など）")
  return parser.parse_args()


def encode_path(path: str) -> str:
  """Encode a directory path the way Claude Code names its project directory."""
  return re.sub(r"[^a-zA-Z0-9]", "-", path)


def resolve_project_dir(options: argparse.Namespace) -> str:
  """Return the history directory selected by -d or -c."""
  if options.direct:
    path = os.path.abspath(os.path.expanduser(options.direct))
    if not os.path.isdir(path):
      sys.exit(f"The directory does not exist: {path}")
    return path

  base = os.path.expanduser(options.cwd)
  # Claude Code records the resolved path, so try it before the logical one
  candidates = [os.path.realpath(base), os.path.abspath(base)]
  for candidate in candidates:
    path = os.path.join(PROJECTS_DIR, encode_path(candidate))
    if os.path.isdir(path):
      return path
  sys.exit(f"History directory not found: {os.path.join(PROJECTS_DIR, encode_path(candidates[0]))}")


def load_records(filepath: str) -> List[dict]:
  """Load JSONL file and return list of parsed records."""
  records = []
  with open(filepath, "r", encoding="utf-8") as f:
    for line in f:
      line = line.strip()
      if not line:
        continue
      try:
        records.append(json.loads(line))
      except json.JSONDecodeError:
        continue
  return records


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
  if not value:
    return None
  try:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
  except ValueError:
    return None


def is_ide_notification(text: str) -> bool:
  text = text.strip()
  return text.startswith("<ide_") and text.endswith(">")


def extract_texts(rec: dict) -> List[str]:
  """Return the text blocks of a user-input record, or an empty list for any other record."""
  if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary"):
    return []
  msg = rec.get("message")
  if not isinstance(msg, dict):
    return []
  content = msg.get("content")
  if isinstance(content, str):
    return [content]
  if isinstance(content, list):
    return [b["text"] for b in content
            if b.get("type") == "text" and not is_ide_notification(b.get("text", ""))]
  return []


def is_human_text(text: str) -> bool:
  """Return False for injected text such as task notifications and interrupts."""
  return not TAG_RE.match(text) and not text.lstrip().startswith("[Request interrupted")


def format_command(text: str) -> Optional[str]:
  """Return '/name args' for a slash command (including skills), otherwise None."""
  name = COMMAND_NAME_RE.search(text)
  if not name:
    return None
  args = COMMAND_ARGS_RE.search(text)
  return f"{name.group(1)} {args.group(1)}".strip() if args else name.group(1)


def describe_prompt(text: str) -> Optional[str]:
  """Return the text to show as a prompt, or None if the text is not one."""
  command = format_command(text)
  if command is not None:
    return None if command.split()[0] in SKIP_COMMANDS else command
  return text if is_human_text(text) else None


def analyze_session(filepath: str) -> Optional[Session]:
  working = timedelta()
  turns = 0
  start: Optional[datetime] = None
  first_prompt = ""
  turn_start: Optional[datetime] = None
  last_ts: Optional[datetime] = None

  for rec in load_records(filepath):
    if rec.get("isSidechain") or rec.get("type") not in RECORD_TYPES:
      continue
    ts = parse_timestamp(rec.get("timestamp"))
    if ts is None:
      continue

    texts = extract_texts(rec)
    if texts:
      if turn_start is not None and last_ts is not None:
        working += last_ts - turn_start
      turn_start = last_ts = ts
      turns += 1
      if start is None:
        start = ts
      for text in texts:
        if not first_prompt:
          first_prompt = describe_prompt(text) or ""
    elif last_ts is not None:
      last_ts = max(last_ts, ts)

  if turn_start is not None and last_ts is not None:
    working += last_ts - turn_start
  if start is None or last_ts is None:
    return None
  session_id = os.path.splitext(os.path.basename(filepath))[0]
  return Session(session_id, start, last_ts, turns, working, first_prompt)


def format_timedelta(td: timedelta) -> str:
  hours, rem = divmod(int(td.total_seconds()), 3600)
  minutes, seconds = divmod(rem, 60)
  return f"{hours}:{minutes:02d}:{seconds:02d}"


def summarize_prompt(text: str, width: int = 40) -> str:
  line = " ".join(text.split())
  return line if len(line) <= width else line[:width] + "..."


def main() -> None:
  options = parse_args()
  project_dir = resolve_project_dir(options)

  sessions = [s for s in (analyze_session(p) for p in glob.glob(os.path.join(project_dir, "*.jsonl"))) if s]
  if not sessions:
    sys.exit(f"No sessions found in: {project_dir}")
  sessions.sort(key=lambda s: s.start)

  print(f"Directory: {project_dir}")
  print()
  print(f"{'Start':<16}  {'Latest':<16}  {'Session':<36}  {'Turns':>5}  {'Working':>8}  Prompt")
  for s in sessions:
    start = s.start.astimezone().strftime("%Y-%m-%d %H:%M")
    latest = s.latest.astimezone().strftime("%Y-%m-%d %H:%M")
    print(f"{start:<16}  {latest:<16}  {s.session_id:<36}  {s.turns:>5}  {format_timedelta(s.working):>8}  {summarize_prompt(s.first_prompt)}")

  total = sum((s.working for s in sessions), timedelta())
  print()
  print(f"Total: {len(sessions)} sessions, {sum(s.turns for s in sessions)} turns, {format_timedelta(total)}")


if __name__ == "__main__":
  main()
