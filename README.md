# claude-master

ClaudeCodeを利用するための設定ファイルを管理するリポジトリです。

## 概要

このリポジトリには、ClaudeCodeで使用する以下のファイルが含まれています：

- **MCP設定ファイル**: MCPサーバーの接続設定
- **CLAUDE.mdサンプル**: ホームディレクトリ用などのコンテキスト定義
- **Agent Skills**: カスタムスキルの拡張

## 必要なツールのインストール

macOS（Homebrew使用）での環境構築手順：

```bash
# uvのインストール（MCP サーバー実行に必要）
brew install uv

# Node.jsのインストール（npx使用に必要）
brew install node
```

## CLAUDE.mdの設定

ClaudeCodeのコンテキストを定義するため、`CLAUDE_MD/`配下のサンプルを配置します。ホームディレクトリ用・プロジェクト用など、用途の異なるサンプルが今後追加される可能性があります。

### 配置方法

配置先はサンプルの用途（ホームディレクトリ用かプロジェクト用か）によって異なります。シンボリックリンクまたはコピーで配置し、どちらを使うかも用途に応じてユーザーが判断してください（例: 複数環境で内容を同期したい場合はシンボリックリンク、配置先ごとに内容を個別にカスタマイズしたい場合はコピー）。

```bash
# 例: basic_CLAUDE.md（ホームディレクトリ用）をシンボリックリンクで配置
ln -sf <claude-master>/CLAUDE_MD/basic_CLAUDE.md ~/.claude/CLAUDE.md

# 例: プロジェクト用サンプルをコピーでプロジェクトルートに配置
cp <claude-master>/CLAUDE_MD/<sample>.md <your-project>/CLAUDE.md
```

### 含まれるサンプル

- `basic_CLAUDE.md`: ホームディレクトリ用（`~/.claude/CLAUDE.md`）の基本的なコンテキストテンプレート

## MCP設定

MCPサーバーへの接続設定です。配置方法（プロジェクトスコープ/ユーザースコープ）、含まれるサーバー一覧、Context7のAPIキー設定などの詳細は[mcp/README.md](mcp/README.md)を参照してください。

## Agent Skillsの設定

カスタムスキルを追加してClaudeCodeの機能を拡張します。スキルはオープン標準（[Agent Skills](https://agentskills.io/)）の形式なので、同じ`SKILL.md`がGitHub Copilot（VS Code、Copilot CLI、cloud agentなど）でも使えます。

### 配置方法

スキルのディレクトリをシンボリックリンクまたはコピーで配置します。どちらを使うかは用途に応じてユーザーが判断してください。

| 種類 | 配置先 | 読み込まれるツール |
|---|---|---|
| プロジェクト用 | `<your-project>/.claude/skills/` | ClaudeCode、GitHub Copilot |
| プロジェクト用 | `<your-project>/.github/skills/` | GitHub Copilot |
| 個人用（全プロジェクト共通） | `~/.claude/skills/` | ClaudeCode、GitHub Copilot |
| 個人用（全プロジェクト共通） | `~/.copilot/skills/` | GitHub Copilot |

`.claude/skills/`に置けば、ClaudeCodeとGitHub Copilotの両方に反映されます。ClaudeCodeでは使わない場合に限り、Copilot専用の`.github/skills/`や`~/.copilot/skills/`も使えます。

```bash
# .claude/skills/ディレクトリが存在しない場合は作成
mkdir -p <your-project>/.claude/skills/

# シンボリックリンクの場合
ln -sf <claude-master>/skills/mermaid-aws-diagram <your-project>/.claude/skills/mermaid-aws-diagram

# コピーの場合
cp -R <claude-master>/skills/mermaid-aws-diagram <your-project>/.claude/skills/mermaid-aws-diagram
```

- 配置先のディレクトリ名は、`SKILL.md`の`name`と同じにしてください。Copilotは一致しないスキルを、エラーを出さずに読み込みません。
- GitHub Copilotがシンボリックリンクを辿るかは、公式ドキュメントに記載がありません。読み込まれない場合はコピーを使ってください。

### 使い方

- **自動**: 依頼内容が`SKILL.md`の`description`に合うと、自動で読み込まれます。
- **手動**: チャットで`/スキル名`と入力します。続けて指示も書けます（例: `/safe-git-commit`）。VS Codeでは`/`だけで一覧が出ます。

詳細は公式ドキュメント（[GitHub Docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)、[VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills)）を参照してください。

### 含まれるスキル

- `mermaid-aws-diagram`: Mermaid形式でAWS構成図を生成するスキル
- `pre-push-secret-scan`: git push前に未公開コミットから機密情報（認証情報、AWSアカウントID、独自ドメイン、メールアドレス等）を検出するスキル
- `safe-git-commit`: 個別ファイル指定または`git add -u`のみ許可する等、安全なgit staging/commitワークフローを提供するスキル

## utilsディレクトリ

ClaudeCodeの利用状況を調べる・作業を補助するスクリプト群です。各スクリプトの使い方は[utils/README.md](utils/README.md)を参照してください。

## ディレクトリ構成

```
claude-master/
├── CLAUDE.md           # このリポジトリ自体の規約
├── CLAUDE_MD/          # CLAUDE.mdのサンプルファイル
│   └── basic_CLAUDE.md
├── mcp/                # MCP設定ファイル
│   ├── README.md
│   └── all.mcp.json
├── skills/             # Agent Skills
│   ├── mermaid-aws-diagram/
│   ├── pre-push-secret-scan/
│   └── safe-git-commit/
├── utils/              # 補助スクリプト
│   ├── README.md
│   └── bin/
│       ├── cc_dir_usage.sh
│       ├── cc_history2md.py
│       ├── cc_times.py
│       └── commit_by_claude.sh
└── tmp/               # 一時ファイル置き場（.gitignoreで除外）
```

## 使い方

設定完了後、ClaudeCodeを起動すれば自動的にMCPサーバーとスキルが読み込まれます。

```bash
claude
```
