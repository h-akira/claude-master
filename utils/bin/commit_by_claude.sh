#!/bin/sh
#
# Created:      2025-09-15 22:24:53
# Usage: commit_by_claude.sh [-j|--japanese]
set -eu

JAPANESE=false
if [ $# -gt 0 ] && ([ "$1" = "-j" ] || [ "$1" = "--japanese" ]); then
  JAPANESE=true
fi

git diff --cached > /tmp/git_diff.txt

if [ ! -s /tmp/git_diff.txt ]; then
  echo "No staged changes to commit"
  rm /tmp/git_diff.txt
  exit 1
fi

if [ "$JAPANESE" = true ]; then
  MESSAGE=$(claude -p "Generate a git commit message in Japanese based on the git diff below. IMPORTANT: Output ONLY the commit message itself with no introductory text, no explanations, no markdown formatting (no backticks), and no references to AI or Claude. Start directly with the commit message. The message should be concise, in imperative mood, and summarize the changes. Git diff:" < /tmp/git_diff.txt)
else
  MESSAGE=$(claude -p "Generate a git commit message in English based on the git diff below. IMPORTANT: Output ONLY the commit message itself with no introductory text, no explanations, no markdown formatting (no backticks), and no references to AI or Claude. Start directly with the commit message. The message should be concise, in imperative mood, and summarize the changes. Git diff:" < /tmp/git_diff.txt)
fi
echo "=== Generated commit message ==="
echo $MESSAGE
echo "================================"
echo "Commit with this message? (y/N): "
read -r CONFIRM

if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
  git commit -m "$MESSAGE"
  echo "Committed successfully!"
else
  echo "Commit cancelled"
fi

rm /tmp/git_diff.txt
