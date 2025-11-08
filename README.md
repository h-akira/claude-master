# claude-master

ClaudeCodeを利用するための設定ファイルを管理するリポジトリです。

## 概要

このリポジトリには、ClaudeCodeで使用するMCP（Model Context Protocol）サーバーの設定が含まれています。

## セットアップ

### 1. 必要なツールのインストール

macOS（Homebrew使用）での環境構築手順：

```bash
# uvのインストール（MCP サーバー実行に必要）
brew install uv

# Node.jsのインストール（npx使用に必要）
brew install node
```

### 2. MCP設定ファイルのコピー

ClaudeCodeの設定ディレクトリにMCP設定ファイルをコピーします：

```bash
# Claude設定ディレクトリを作成（存在しない場合）
mkdir -p ~/.claude

# MCP設定ファイルをコピー
cp dot.mcp.json ~/.claude/mcp.json
```

### 3. API キーの設定（必要に応じて）

`~/.claude/mcp.json`を編集し、必要なAPIキーを設定してください：

```json
"context7": {
  "env": {
    "CONTEXT7_API_KEY": "YOUR_API_KEY"  // 実際のAPIキーに置き換え
  }
}
```

## 含まれるMCPサーバー

- **awslabs.cdk-mcp-server**: AWS CDKのサポート
- **awslabs.aws-documentation-mcp-server**: AWSドキュメントへのアクセス
- **awslabs.aws-diagram-mcp-server**: AWS構成図の生成
- **context7**: コンテキスト管理ツール

## 使い方

設定完了後、ClaudeCodeを起動すれば自動的にMCPサーバーが読み込まれます。

```bash
claude
```
