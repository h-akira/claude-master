# claude-master

ClaudeCodeを利用するための設定ファイルを管理するリポジトリです。

## 概要

このリポジトリには、ClaudeCodeで使用する以下のファイルが含まれています：

- **MCP設定ファイル**: MCPサーバーの接続設定
- **CLAUDE.mdサンプル**: プロジェクト固有のコンテキスト定義
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

プロジェクト固有のコンテキストを定義するため、CLAUDE.mdサンプルをプロジェクトのルートディレクトリに配置します。

### 配置方法

シンボリックリンクを使用して配置します：

```bash
# プロジェクトルートでの作業を想定
cd <your-project>

# シンボリックリンクを作成
ln -sf <claude-master>/CLAUDE_md/basic_CLAUDE.md CLAUDE.md
```

### 含まれるサンプル

- `basic_CLAUDE.md`: 基本的なプロジェクトコンテキストのテンプレート

## MCP設定

MCPサーバーへの接続設定を行います。

### 配置方法

MCP設定ファイルをプロジェクトのルートディレクトリにコピーして編集します：

```bash
# プロジェクトルートにMCP設定ファイルをコピー
cp <claude-master>/mcp_json/all.mcp.json <your-project>/.mcp.json

# 必要に応じて編集（特にAPIキーなど）
```

### Context7のAPIキー設定

Context7を使用する場合は、`<your-project>/.mcp.json`を編集してAPIキーを設定してください：

```json
"context7": {
  "env": {
    "CONTEXT7_API_KEY": "YOUR_API_KEY"  // 実際のAPIキーに置き換え
  }
}
```

### 含まれるMCPサーバー

| サーバー名 | 説明 |
|-----------|------|
| [awslabs.cdk-mcp-server](https://github.com/awslabs/mcp/tree/main/src/cdk-mcp-server) | AWS CDKのサポート |
| [awslabs.aws-documentation-mcp-server](https://github.com/awslabs/mcp/tree/main/src/aws-documentation-mcp-server) | AWSドキュメントへのアクセス |
| [awslabs.aws-diagram-mcp-server](https://github.com/awslabs/mcp/tree/main/src/aws-diagram-mcp-server) | AWS構成図の生成 |
| [context7](https://github.com/upstash/context7) | コンテキスト管理ツール |

## Agent Skillsの設定

カスタムスキルを追加してClaudeCodeの機能を拡張します。

### 配置方法

シンボリックリンクを使用して`.claude/skills/`ディレクトリに配置します：

```bash
# .claude/skills/ディレクトリが存在しない場合は作成
mkdir -p <your-project>/.claude/skills/

# スキルのシンボリックリンクを作成
ln -sf <claude-master>/skills/mermaid-aws-diagram <your-project>/.claude/skills/mermaid-aws-diagram
```

### 含まれるスキル

- `mermaid-aws-diagram`: Mermaid形式でAWS構成図を生成するスキル

## ディレクトリ構成

```
claude-master/
├── CLAUDE_md/          # CLAUDE.mdのサンプルファイル
│   └── basic_CLAUDE.md
├── mcp_json/           # MCP設定ファイル
│   └── all.mcp.json
└── skills/             # Agent Skills
    └── mermaid-aws-diagram/
```

## 使い方

設定完了後、ClaudeCodeを起動すれば自動的にMCPサーバーとスキルが読み込まれます。

```bash
claude
```
