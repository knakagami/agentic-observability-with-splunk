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
│   └── switch-version.sh                    # バージョン切り替えスクリプト
├── services/
│   ├── order-service/
│   │   ├── main.py                          # FastAPI + OTel + JSON logs
│   │   ├── load_generator.py                # Continuous traffic (60% integer amounts)
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── payment-service/
│       ├── main.py                          # 現在デプロイ中のバージョン
│       ├── main_v1.0_normal.py              # v1.0: 正常版
│       ├── main_v1.1_bug.py                 # v1.1: ZeroDivisionError バグあり
│       ├── main_v1.2_fix.py                 # v1.2: 修正済み
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── order-service/
│   ├── payment-service/
│   └── load-generator/
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

### 4. Detector 作成

```bash
export SPLUNK_O11Y_TOKEN=<your-token>
python detector/create_detector.py
```

### 5. MCP設定

`mcp-settings-template.json` を参考に `~/.claude/settings.json` にMCPサーバー設定を追加してください。

---

## バージョン切り替え

`scripts/switch-version.sh` で payment-service のバージョンを切り替えられます。
`main.py` の差し替えと `deployment.yaml` のバージョン更新・push までを自動実行します。

```bash
# デモ前のリセット（v1.0 正常版）
./scripts/switch-version.sh v1.0

# バグ導入（エラー率急上昇シナリオ）
./scripts/switch-version.sh v1.1

# 修正版デプロイ（回復シナリオ）
./scripts/switch-version.sh v1.2
```

---

## デモシナリオ

### バグの内容 (v1.1)

`payment-service` で `payment.amount` が整数のとき `ZeroDivisionError` が発生します。

```python
decimal_part = payment.amount - int(payment.amount)  # → 0 for whole numbers
discount_rate = payment.amount / decimal_part         # → ZeroDivisionError!
```

Load Generatorは60%の確率で整数金額を送るため、エラー率が約60%に急上昇します。

### デモフロー (10〜15分)

1. `./scripts/switch-version.sh v1.0` で正常状態を確認
2. `./scripts/switch-version.sh v1.1` でバグ導入
3. GitHub Actions デプロイ完了 → O11y にデプロイマーカー表示
4. エラー率急上昇 → Detector アラート発火
5. Claude (Obs Cloud MCP): エラー率メトリクス確認・失敗トレース特定
6. Claude (Splunk MCP): SPLでスタックトレース抽出・ZeroDivisionError 特定
7. Claude (Splunk MCP): 「整数金額のみが失敗」パターンを統計的に証明
8. Claude (GitHub MCP): 修正PRを作成 (v1.2)
9. PRマージ → デプロイ → エラー率0%への回復を確認

### デモ後のリセット

```bash
./scripts/switch-version.sh v1.0
```

---

## OTel リソース属性

| 属性 | 値 | 設定場所 |
|------|-----|---------|
| `service.name` | `order-service` / `payment-service` | k8s deployment env `OTEL_SERVICE_NAME` |
| `deployment.environment` | `agentic-o11y` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.version` | `1.0` / `1.1` / `1.2` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.namespace` | `agentic-o11y-mcp` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
