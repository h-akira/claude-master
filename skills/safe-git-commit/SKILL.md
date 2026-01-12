---
name: safe-git-commit
description: Safe git staging and commit workflow with strict constraints. Use when staging changes or creating commits. Enforces individual file staging or git add -u only (never git add . or -A), requires user confirmation before commits, generates clear English commit messages, and never pushes to remote. Prevents accidental staging of build artifacts or binary files.
---

# Safe Git Commit

## Overview

Provides a controlled workflow for staging changes and creating git commits with safety constraints to prevent common mistakes.

## Core Workflow

Follow these steps in order:

### 1. Check Repository Status

Always start by understanding the current state:

```bash
git status
git diff --cached  # Check already staged files
```

Review:
- Modified tracked files
- New untracked files
- Already staged changes
- Current branch

### 2. Stage Changes

**Allowed staging methods:**

**For modified tracked files:**
```bash
git add -u
```

**For new files (individual selection only):**
```bash
git add path/to/specific/file.ext
```

**Prohibited commands:**
- `git add .` - NEVER use
- `git add -A` - NEVER use
- `git add *` - NEVER use

### 3. File Selection Criteria

When selecting new files to stage:

**Include:**
- Source code files (.js, .ts, .py, .java, etc.)
- Configuration files (.json, .yaml, .toml, etc.)
- Documentation (.md, .txt)
- Tests
- Files mentioned in conversation history

**Exclude:**
- Build artifacts (dist/, build/, target/, *.o, *.class)
- Binary files (*.exe, *.dll, *.so, *.dylib)
- Compiled code (*.pyc, *.pyo, __pycache__/)
- Dependencies (node_modules/, vendor/)
- IDE files (.DS_Store, *.swp, .vscode/, .idea/)
- Files matching .gitignore patterns
- Log files
- Temporary files

**Check conversation history** for context about which files were intentionally created.

### 4. Review Staged Changes

Before committing, verify what will be committed:

```bash
git diff --cached
git status
```

### 5. Generate Commit Message

Create a clear, descriptive commit message in English:

**Format:**
- First line: Concise summary (50 chars or less)
- Body (if needed): Detailed explanation

**Style:**
- Use imperative mood ("Add feature" not "Added feature")
- Be specific about what changed and why
- No references to AI, automation tools, or assistant
- Focus on the change itself, not how it was made

**Examples:**
```
Add user authentication middleware

Refactor database connection pool
- Reduce connection timeout
- Add retry logic for failed connections

Fix memory leak in image processing
```

### 6. Present for User Approval

Before executing the commit, present:

1. List of files to be committed
2. Proposed commit message
3. Brief summary of changes

**Wait for explicit user approval** before proceeding.

### 7. Create Commit

After user approval:

```bash
git commit -m "Your commit message"
```

**NEVER execute `git push` or `git push origin <branch>`** - users handle pushing manually.

## Safety Checks

Before staging any file:

1. ✓ Is it tracked or a legitimate new file?
2. ✓ Is it in .gitignore?
3. ✓ Is it a build artifact or binary?
4. ✓ Was it mentioned in conversation or explicitly created?
5. ✓ Is git add -u sufficient for tracked file changes?

Before committing:

1. ✓ Reviewed staged changes with git diff --cached
2. ✓ Generated appropriate commit message
3. ✓ Received explicit user approval

## Example Workflow

```bash
# 1. Check status
git status
git diff --cached

# 2. Stage changes
# If only modified tracked files:
git add -u

# If new files need staging:
git add src/auth.js
git add tests/auth.test.js

# 3. Review what will be committed
git diff --cached
git status

# 4. Present to user for approval:
# "Ready to commit the following changes:
#  - src/auth.js (new authentication module)
#  - tests/auth.test.js (authentication tests)
#
# Proposed message: 'Add user authentication module'
#
# Proceed with commit? [Wait for approval]"

# 5. After approval, commit
git commit -m "Add user authentication module"

# 6. Confirm completion
git log -1 --oneline
```

## Common Scenarios

**Scenario: User says "commit my changes"**
1. Run git status and git diff --cached
2. Check conversation for context on what was changed
3. Stage with git add -u if only tracked files modified
4. If new files exist, identify which should be committed
5. Generate commit message
6. Present for approval
7. Commit after approval

**Scenario: User specifies files to commit**
1. Verify files exist and are appropriate
2. Stage individual files with git add <file>
3. Review staged changes
4. Generate commit message
5. Present for approval
6. Commit after approval

**Scenario: Some files already staged**
1. Check git diff --cached to see staged files
2. Determine if additional files need staging
3. Stage additional files if needed
4. Generate commit message for all staged changes
5. Present for approval
6. Commit after approval
