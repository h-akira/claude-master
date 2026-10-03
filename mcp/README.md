# MCP設定

MCPサーバーへの接続設定です。[公式ドキュメント](https://code.claude.com/docs/en/mcp)によると、MCPサーバーの設定には主に次の2つのスコープがあります。

| スコープ | 読み込み範囲 | チーム共有 | 保存場所 |
|---|---|---|---|
| プロジェクト | 現在のプロジェクトのみ | あり（git管理） | プロジェクト直下の`.mcp.json` |
| ユーザー | 全プロジェクト | なし | `~/.claude.json`（コマンド経由でのみ登録可能） |

## プロジェクトスコープで使う場合

`.mcp.json`はプロジェクト直下に置く設定ファイルです。シンボリックリンクかコピーかは用途に応じて判断してください（例: APIキーなどプロジェクトごとに内容を変えたい場合はコピー、複数プロジェクトで全く同じ設定を共有したい場合はシンボリックリンク）。

```bash
# コピーの場合
cp <claude-master>/mcp/all.mcp.json <your-project>/.mcp.json

# シンボリックリンクの場合
ln -sf <claude-master>/mcp/all.mcp.json <your-project>/.mcp.json

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

## ユーザースコープで使う場合（全プロジェクト共通）

ユーザースコープは`.mcp.json`のようにファイルを配置する方式ではなく、`claude mcp add`コマンドで登録するのが公式な方法です（保存先の`~/.claude.json`はMCP設定専用ファイルではなく他の設定も混在するため、`all.mcp.json`をそのままコピー・シンボリックリンクすることはできません）。

`all.mcp.json`と同じ内容を登録する場合のコマンドは以下の通りです：

```bash
claude mcp add --scope user --transport stdio awslabs.cdk-mcp-server \
  --env FASTMCP_LOG_LEVEL=ERROR \
  -- uvx awslabs.cdk-mcp-server@latest

claude mcp add --scope user --transport stdio awslabs.aws-documentation-mcp-server \
  --env FASTMCP_LOG_LEVEL=ERROR \
  --env AWS_DOCUMENTATION_PARTITION=aws \
  --env MCP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36" \
  -- uvx awslabs.aws-documentation-mcp-server@latest

claude mcp add --scope user --transport stdio awslabs.aws-diagram-mcp-server \
  --env FASTMCP_LOG_LEVEL=ERROR \
  -- uvx awslabs.aws-diagram-mcp-server

claude mcp add --scope user --transport stdio context7 \
  --env CONTEXT7_API_KEY=YOUR_API_KEY \
  -- npx -y @upstash/context7-mcp
```

登録後は`claude mcp list`で状態を確認できます。

## 含まれるMCPサーバー

| サーバー名 | 説明 |
|-----------|------|
| [awslabs.cdk-mcp-server](https://github.com/awslabs/mcp/tree/main/src/cdk-mcp-server) | AWS CDKのサポート |
| [awslabs.aws-documentation-mcp-server](https://github.com/awslabs/mcp/tree/main/src/aws-documentation-mcp-server) | AWSドキュメントへのアクセス |
| [awslabs.aws-diagram-mcp-server](https://github.com/awslabs/mcp/tree/main/src/aws-diagram-mcp-server) | AWS構成図の生成 |
| [context7](https://github.com/upstash/context7) | コンテキスト管理ツール |
