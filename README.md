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
├── services/
│   ├── order-service/
│   │   ├── main.py                          # FastAPI + OTel + JSON logs
│   │   ├── load_generator.py                # Continuous traffic (60% integer amounts)
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── payment-service/
│       ├── main.py                          # v1.0: normal (deployed to main)
│       ├── main_v1.1_bug.py                 # v1.1: ZeroDivisionError bug (copy to main.py for bug branch)
│       ├── main_v1.2_fix.py                 # v1.2: fixed (copy to main.py for fix branch)
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/
│   ├── namespace.yaml
│   ├── order-service/
│   ├── payment-service/
│   └── load-generator/
├── detector/create_detector.py              # Create Splunk O11y detector via API
├── splunk/spl_queries.md                    # SPL queries for demo investigation
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

## デモシナリオ

| ブランチ | 内容 |
|---------|------|
| `main` | v1.0 正常版 |
| `feature/v1.1-payment-bug` | v1.1 バグあり (`main.py` を `main_v1.1_bug.py` の内容に差し替え) |
| `fix/payment-division-error` | v1.2 修正版 (`main.py` を `main_v1.2_fix.py` の内容に差し替え) |

### バグの内容 (v1.1)

`payment-service` で `payment.amount` が整数のとき `ZeroDivisionError` が発生します。

```python
decimal_part = payment.amount - int(payment.amount)  # → 0 for whole numbers
discount_rate = payment.amount / decimal_part         # → ZeroDivisionError!
```

Load Generatorは60%の確率で整数金額を送るため、エラー率が約60%に急上昇します。

---

## デモフロー (10〜15分)

1. v1.0 正常動作を Splunk O11y ダッシュボードで確認
2. `feature/v1.1-payment-bug` ブランチのPRをマージ
3. GitHub Actions デプロイ完了 → O11y にデプロイマーカー表示
4. エラー率急上昇 → Detector アラート発火
5. Claude (Obs Cloud MCP): エラー率メトリクス確認・失敗トレース特定
6. Claude (Splunk MCP): SPLでスタックトレース抽出・ZeroDivisionError 特定
7. Claude (Splunk MCP): 「整数金額のみが失敗」パターンを統計的に証明
8. Claude (GitHub MCP): 修正PRを作成 (v1.2)
9. PRマージ → デプロイ
10. Claude (Obs Cloud MCP): エラー率0%への回復を確認
