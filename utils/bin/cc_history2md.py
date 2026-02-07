#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Created: 2026-02-07 22:33:08

import sys
import os
import json

def parse_args():
  import argparse
  parser = argparse.ArgumentParser(description="""\
ClaudeCodeの会話履歴ファイル（セッションID.jsonl）を読み、これをマークダウンに整形してファイル出力する
""", formatter_class = argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--version", action="version", version='%(prog)s 0.0.1')
  parser.add_argument("-o", "--output", metavar="output-file", default="history.md", help="output file")
  parser.add_argument("-y", "--yes", action="store_true", help="ファイルの上書き確認を無視")
  parser.add_argument("-u", "--user-only", action="store_true", help="ユーザーの入力のみ")
  parser.add_argument("-t", "--no-tool", action="store_true", help="ツール呼び出しと実行結果を含めない")
  parser.add_argument("-i", "--no-info", action="store_true", help="先頭のセッション情報を含めない")
  parser.add_argument("file", metavar="input-file", help="input file")
  options = parser.parse_args()
  if not os.path.isfile(options.file):
    raise Exception("The input file does not exist.")
  return options


def load_records(filepath):
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


def extract_session_info(records):
  """Extract session metadata from records."""
  info = {
    "session_id": None,
    "cwd": None,
    "model": None,
    "timestamp": None,
  }
  for rec in records:
    if rec.get("sessionId") and not info["session_id"]:
      info["session_id"] = rec["sessionId"]
    if rec.get("cwd") and not info["cwd"]:
      info["cwd"] = rec["cwd"]
    if rec.get("timestamp") and not info["timestamp"]:
      info["timestamp"] = rec["timestamp"]
    msg = rec.get("message", {})
    if msg.get("model") and not info["model"]:
      info["model"] = msg["model"]
  return info


def is_ide_notification(text):
  """Check if text is an IDE-generated notification."""
  return text.strip().startswith("<ide_") and text.strip().endswith(">")


def format_tool_input(name, inp):
  """Format tool input for markdown display."""
  lines = []
  if name == "Bash":
    desc = inp.get("description", "")
    cmd = inp.get("command", "")
    if desc:
      lines.append(f"*{desc}*")
    lines.append(f"```bash\n{cmd}\n```")
  elif name == "Read":
    path = inp.get("file_path", "")
    lines.append(f"File: `{path}`")
  elif name == "Write":
    path = inp.get("file_path", "")
    lines.append(f"File: `{path}`")
    content = inp.get("content", "")
    if content:
      lines.append(f"```\n{content}\n```")
  elif name == "Edit":
    path = inp.get("file_path", "")
    old = inp.get("old_string", "")
    new = inp.get("new_string", "")
    lines.append(f"File: `{path}`")
    if old:
      lines.append(f"```diff\n- {old}\n+ {new}\n```")
  elif name == "Glob":
    pattern = inp.get("pattern", "")
    path = inp.get("path", "")
    lines.append(f"Pattern: `{pattern}`" + (f" in `{path}`" if path else ""))
  elif name == "Grep":
    pattern = inp.get("pattern", "")
    path = inp.get("path", "")
    lines.append(f"Pattern: `{pattern}`" + (f" in `{path}`" if path else ""))
  elif name == "Task":
    desc = inp.get("description", "")
    prompt = inp.get("prompt", "")
    lines.append(f"*{desc}*" if desc else "")
    if prompt:
      lines.append(f"> {prompt[:200]}{'...' if len(prompt) > 200 else ''}")
  else:
    # Generic: show all input as JSON
    lines.append(f"```json\n{json.dumps(inp, ensure_ascii=False, indent=2)}\n```")
  return "\n".join(lines)


def render_markdown(records, options):
  """Convert records to markdown string."""
  info = extract_session_info(records)
  lines = []

  # Header
  lines.append("# Claude Code Session")
  lines.append("")
  if not options.no_info:
    session_id = info["session_id"] or "unknown"
    lines.append(f"| | |")
    lines.append(f"|---|---|")
    lines.append(f"| **Session** | `{session_id}` |")
    if info["timestamp"]:
      lines.append(f"| **Date** | {info['timestamp'][:10]} |")
    if info["model"]:
      lines.append(f"| **Model** | {info['model']} |")
    if info["cwd"]:
      lines.append(f"| **Working Directory** | `{info['cwd']}` |")
    lines.append("")

  # Track the last rendered assistant message ID to avoid duplicate headers
  last_assistant_msg_id = None
  need_separator = bool(lines)  # skip first separator when --no-info

  def append_separator():
    nonlocal need_separator
    if need_separator:
      lines.append("---")
      lines.append("")
    need_separator = True

  for rec in records:
    rec_type = rec.get("type")

    # Skip metadata records
    if rec_type in ("queue-operation", "file-history-snapshot"):
      continue

    # Skip error messages
    if rec.get("isApiErrorMessage"):
      continue

    msg = rec.get("message", {})
    if not isinstance(msg, dict):
      continue
    role = msg.get("role")
    content_blocks = msg.get("content", [])

    # content can be a string (e.g. context continuation summary)
    if isinstance(content_blocks, str):
      if rec_type == "user" and role == "user":
        append_separator()
        lines.append("**User**")
        lines.append("")
        lines.append(content_blocks)
        lines.append("")
      elif rec_type == "assistant" and role == "assistant" and not options.user_only:
        append_separator()
        lines.append("**Assistant**")
        lines.append("")
        lines.append(content_blocks)
        lines.append("")
      continue

    if not isinstance(content_blocks, list):
      continue

    if rec_type == "user" and role == "user":
      # Check if this is a tool result
      has_tool_result = any(b.get("type") == "tool_result" for b in content_blocks)
      has_text = any(b.get("type") == "text" for b in content_blocks)

      if has_text:
        # Render user text messages
        for block in content_blocks:
          if block.get("type") == "text":
            text = block["text"]
            if is_ide_notification(text):
              continue
            append_separator()
            lines.append("**User**")
            lines.append("")
            lines.append(text)
            lines.append("")

      if has_tool_result and not options.user_only and not options.no_tool:
        tool_result = rec.get("toolUseResult", {})
        if isinstance(tool_result, str):
          output = tool_result
        else:
          stdout = tool_result.get("stdout", "")
          stderr = tool_result.get("stderr", "")
          output = stdout
          if stderr:
            output = output + "\n[stderr]\n" + stderr if output else "[stderr]\n" + stderr
        if output:
          lines.append("<details>")
          lines.append("<summary>Result</summary>")
          lines.append("")
          lines.append(f"```\n{output}\n```")
          lines.append("")
          lines.append("</details>")
          lines.append("")

    elif rec_type == "assistant" and role == "assistant":
      if options.user_only:
        continue

      current_msg_id = msg.get("id", "")

      for block in content_blocks:
        if block.get("type") == "text":
          text = block["text"]
          if not text.strip():
            continue
          # Print separator only if new message
          if current_msg_id != last_assistant_msg_id:
            append_separator()
            lines.append("**Assistant**")
            lines.append("")
            last_assistant_msg_id = current_msg_id
          lines.append(text)
          lines.append("")

        elif block.get("type") == "tool_use" and not options.no_tool:
          tool_name = block.get("name", "")
          tool_input = block.get("input", {})
          if current_msg_id != last_assistant_msg_id:
            append_separator()
            lines.append("**Assistant**")
            lines.append("")
            last_assistant_msg_id = current_msg_id
          lines.append(f"**Tool: {tool_name}**")
          lines.append("")
          lines.append(format_tool_input(tool_name, tool_input))
          lines.append("")

  return "\n".join(lines)


def main():
  options = parse_args()

  # Confirm overwrite if output file exists
  if os.path.isfile(options.output) and not options.yes:
    answer = input(f"'{options.output}' already exists. Overwrite? [y/N]: ")
    if answer.lower() != "y":
      print("Aborted.")
      sys.exit(0)

  records = load_records(options.file)
  md = render_markdown(records, options)

  with open(options.output, "w", encoding="utf-8") as f:
    f.write(md)

  print(f"Written to {options.output} ({len(records)} records processed)")


if __name__ == '__main__':
  main()
