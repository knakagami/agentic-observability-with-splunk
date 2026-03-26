# Agentic Observability with Splunk

イベント登壇・販売デモ用リポジトリ。
**Splunk MCP + Splunk Observability Cloud MCP + GitHub MCP** を使ったアジェンティックな障害対応フローを実演します。

```
デプロイ → 異常検出 → 原因調査 → コード修正 → リリース → 回復確認
```

---

## アーキテクチャ

```
order-service (FastAPI) ──calls──> payment-service (FastAPI)
       │                                    │
       └──── OpenTelemetry SDK ─────────────┘
                      │
        Splunk Distro OTel Collector (既存、default namespace)
        ├── traces/metrics ──> Splunk Observability Cloud (jp0)
        └── logs ──────────> Splunk Enterprise (HEC)

GitHub Actions: commit → SSH into K3s VM (port 2222) → git pull → docker build → k3s ctr import → kubectl apply → deploy annotation
```

---

## ファイル構造

```
.
├── .github/workflows/build-and-deploy.yml   # CI/CD: SSH deploy to K3s
├── scripts/
│   └── demo-reset.sh                        # デモ後リセットスクリプト
├── services/
│   ├── order-service/
│   │   ├── main.py                          # FastAPI + OTel + JSON logs
│   │   ├── load_generator.py                # Continuous traffic (60% integer amounts)
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── payment-service/
│       ├── main.py                          # 現在デプロイ中のバージョン
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── order-service/
│   ├── payment-service/
│   └── load-generator/
├── .cursor/rules/                           # Cursor デモ運用ルール（MCP・SPL）
├── detector/create_detector.py              # Splunk O11y Detector作成スクリプト
├── splunk/spl_queries.md                    # デモ中にClaudeが使うSPLクエリ集
└── mcp-settings-template.json              # ~/.claude/settings.json template
```

---

## セットアップ手順

### 1. GitHub Secrets の登録

| Secret名 | 内容 |
|---------|------|
| `K3S_VM_HOST` | K3s VMのIPアドレス |
| `K3S_VM_USER` | SSHユーザー名 |
| `K3S_SSH_KEY` | SSH秘密鍵 |
| `SPLUNK_O11Y_TOKEN` | Splunk Observability Cloudアクセストークン (デプロイイベント送信用) |

### 2. K3s VM の初期セットアップ

```bash
# K3s VMにSSHして実行
git clone https://github.com/knakagami/agentic-observability-with-splunk.git
cd agentic-observability-with-splunk

# Namespace作成
sudo kubectl create namespace agentic-o11y-mcp
```

### 3. 初回デプロイ

```bash
git push origin main  # → GitHub Actions が自動実行
```

### 4. デモ用タグの作成（初回のみ・クリーンアップPR マージ後に実行）

```bash
git fetch origin
git tag v1.0-demo-base origin/main
git push origin v1.0-demo-base
```

> `demo-reset.sh` はこのタグを基点として `main` をリセットします。

### 5. Detector 作成

```bash
export SPLUNK_O11Y_TOKEN=<your-token>
python detector/create_detector.py
```

### 6. MCP設定

`mcp-settings-template.json` を参考に `~/.claude/settings.json` にMCPサーバー設定を追加してください。

---

## エージェント・ファシリテーター運用（デモ実演時）

- **`feature` / `fix` を `main` に取り込む操作は GitHub MCP で PR をマージする**（デモ手順としてローカルでの `git merge` + `push` は使わない）。
- **ファシリテーター向け:** 調査を依頼するときはチャネルを明示する（例: 「Splunk Observability Cloud でトレースを確認して」「Splunk Enterprise のログで KeyError を探して」）。エージェントが README やルールを理由に調査範囲を勝手に広げないようにする。

---

## デモ用ブランチ構成

バージョン管理はブランチで行います。各バージョンの差分は対応するブランチの PR で確認できます。

```
main  ←─────────────────────────────────── v1.0 ベースライン（デモ前後は常にここ）
  └── feature/payment-decimal-discount  ─── v1.1: discount機能追加（バグあり）
        └── fix/payment-division-by-zero ── v1.2: KeyError 修正
```

| ブランチ | 内容 | PRでの役割 |
|---------|------|-----------|
| `main` | v1.0 正常版 | ベースライン |
| `feature/payment-decimal-discount` | v1.1 バグあり | デモ中にマージ → バグ導入 |
| `fix/payment-division-by-zero` | v1.2 修正版 | Claude が GitHub MCP でマージ → 回復 |

---

## デモシナリオ

### バグの内容 (v1.1)

`payment-service` で `payment.amount` が整数のとき `KeyError: 0` が発生します。

```python
DISCOUNT_RATES = {1: 0.01, 2: 0.02, ..., 9: 0.09}  # key 0 が存在しない

decimal_part = payment.amount - int(payment.amount)  # → 0.0 for whole numbers
tier_key = round(decimal_part * 10)                  # → 0
discount_rate = DISCOUNT_RATES[tier_key]             # → KeyError: 0 !
```

Load Generatorは60%の確率で整数金額を送るため、エラー率が約60%に急上昇します。

### デモフロー (10〜15分)

1. main が v1.0 の状態であることを確認
2. **`feature/payment-decimal-discount` → main の PR をマージ** → v1.1 デプロイ
3. GitHub Actions デプロイ完了 → O11y にデプロイマーカー表示
4. エラー率急上昇 → Detector アラート発火
5. Claude (Obs Cloud MCP): エラー率メトリクス確認・失敗トレース特定
6. Claude (Splunk MCP): SPLでスタックトレース抽出・`KeyError: 0` 特定
7. Claude (Splunk MCP): 「整数金額のみが失敗」パターンを統計的に証明
8. **Claude (GitHub MCP): `fix/payment-division-by-zero` → main の PR を作成・マージ** → v1.2 デプロイ
9. エラー率0%への回復を確認

### デモ後のリセット

```bash
./scripts/demo-reset.sh
```

スクリプトは `main` を `v1.0-demo-base` タグに force reset し、**`git push -f origin main` します**。`main` への push のため **[Build and Deploy](.github/workflows/build-and-deploy.yml)** ワークフローが自動で起動し、K3s VM へ v1.0 の再デプロイが走ります。**GitHub Actions でワークフローが成功したこととロールアウト完了を確認**してください。失敗時や再実行が必要な場合は、同ワークフローの **workflow_dispatch**（手動実行）も利用できます。

その後、GitHub で `feature/payment-decimal-discount` → `main` の PR を再作成してください。

> **注:** `fix/payment-division-by-zero` → `main` の PR はデモ中に GitHub MCP でマージする想定のため、再作成不要です。

---

## OTel リソース属性

| 属性 | 値 | 設定場所 |
|------|-----|---------|
| `service.name` | `order-service` / `payment-service` | k8s deployment env `OTEL_SERVICE_NAME` |
| `deployment.environment` | `agentic-o11y` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.version` | `1.0` / `1.1` / `1.2` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.namespace` | `agentic-o11y-mcp` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
