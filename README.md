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

### 2. MCP設定ファイルの配置

このリポジトリから任意の`*.mcp.json`を選んでプロジェクトのルートディレクトリにコピーします：

```bash
# プロジェクトルートにMCP設定ファイルをコピー
cp <任意の*.mcp.json> <your-project>/.mcp.json
```

### 3. API キーの設定（必要に応じて）

`<your-project>/.mcp.json`を編集し、必要なAPIキーを設定してください：

```json
"context7": {
  "env": {
    "CONTEXT7_API_KEY": "YOUR_API_KEY"  // 実際のAPIキーに置き換え
  }
}
```

## 含まれるMCPサーバー

| サーバー名 | 説明 | GitHub |
|-----------|------|--------|
| awslabs.cdk-mcp-server | AWS CDKのサポート | [リンク](https://github.com/awslabs/mcp/tree/main/src/cdk-mcp-server) |
| awslabs.aws-documentation-mcp-server | AWSドキュメントへのアクセス | [リンク](https://github.com/awslabs/mcp/tree/main/src/aws-documentation-mcp-server) |
| awslabs.aws-diagram-mcp-server | AWS構成図の生成 | [リンク](https://github.com/awslabs/mcp/tree/main/src/aws-diagram-mcp-server) |
| context7 | コンテキスト管理ツール | [リンク](https://github.com/upstash/context7) |

## 使い方

設定完了後、ClaudeCodeを起動すれば自動的にMCPサーバーが読み込まれます。

```bash
claude
```
