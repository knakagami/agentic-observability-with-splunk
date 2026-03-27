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

GitHub Actions: commit → SSH into K3s VM (port 2222) → git fetch/reset to origin/main → docker build → k3s ctr import → kubectl apply → deploy annotation
```

---

## ファイル構造

```
.
├── .github/workflows/build-and-deploy.yml   # CI/CD: SSH deploy to K3s
├── scripts/
│   ├── demo-reset.sh                        # デモ後: main を demo/v1.0-base に合わせる
│   └── refresh-demo-branches.sh             # feature/fix にベースラインを取り込む（任意）
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
| `SPLUNK_O11Y_TOKEN` | **Splunk Observability Cloud** の組織アクセストークン（ingest 用。ワークフローは `ingest.jp0.signalfx.com` 向け。**HEC トークンや別レルムのトークンでは 401** になります） |

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

### 4. デモ用ベースライン枝 `demo/v1.0-base`（初回・`main` を v1.0 にした直後）

`demo-reset.sh` は **`origin/demo/v1.0-base`** を基点に `main` をリセットします。`main` が **v1.0** のときだけ、リモートのベースライン枝を更新（初回は作成）します。

```bash
git fetch origin
git push origin main:demo/v1.0-base
```

> **注意:** v1.1 / v1.2 が入った `main` で上書きしないこと。通常は **`demo-reset.sh` 実行後**、または v1.0 に戻した直後に更新する。

### 5. Detector 作成

```bash
export SPLUNK_O11Y_TOKEN=<your-token>
python detector/create_detector.py
```

### 6. MCP設定

`mcp-settings-template.json` を参考に `~/.claude/settings.json` にMCPサーバー設定を追加してください。

---

## エージェント・ファシリテーター運用（デモ実演時）

- **`feature` / `fix` を `main` に取り込む操作は GitHub MCP で PR をマージする**（ローカルでの `git merge` + `push` は使わない）。
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

### リポジトリのメンテナンス順序（推奨）

共通ファイル（`README.md`、`.cursor/rules/`、`scripts/`、`splunk/`、`.github/workflows/`、負荷系の `load_generator` / `k8s/load-generator` など）を直すときは、**長命ブランチへばらまく前に「正」とするコミットを決める**と差分が追いやすいです。

1. **`main` が v1.0** の状態で変更をコミットし `push` する（通常は `demo-reset` 直後の `main`）。
2. **`demo/v1.0-base` を `main` に揃える:** `git push origin main:demo/v1.0-base`（上書き注意: `main` が v1.0 であること）。
3. **`feature` / `fix` へ反映:** `./scripts/refresh-demo-branches.sh` でドライランを確認し、必要なら `--apply` で `origin/demo/v1.0-base` を各ブランチにマージしてから `git push`。履歴を畳みたい場合はスクリプトが表示する **cherry-pick / force-push 代替**を検討。
4. **`demo-reset` のあと**は `fix` が古い v1.2 を指しうるため、**次回デモ前に必ず 3 を実行**するか、同等のマージを手で行う。

**代替案（復旧の見せ方）:** 復旧を「fix ブランチの PR」ではなく **`git revert` で v1.1 マージコミットを打ち消す**運用もある。PR で変更履歴を見せたい場合は向かないことがある。

**Detector:** 「サービスエラー率」の検知は例外種別で絞れないことが多い。ノイズが多い場合はアプリ／クライアント側の改善（例: load-generator のリトライ・ヘルス待ち）に加え、組織のルールで **例外タイプに基づく別 Detector** を検討する。

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

Load Generator は 60% の確率で整数金額を送るため、**v1.1 の POST /pay について**エラー率が約 60% に急上昇します（小数リクエストは成功しうる）。リクエスト間隔は環境変数 `REQUEST_INTERVAL_SECONDS`（既定 0.5 秒）で変えられるため **絶対 RPS は変わるが、整数／小数の比率は同じ**です。

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

スクリプトは **`origin/demo/v1.0-base` と同じコミット**に `main` を hard reset し、**`git push -f origin main` します**。`main` への push のため **[Build and Deploy](.github/workflows/build-and-deploy.yml)** ワークフローが自動で起動し、K3s VM へ v1.0 の再デプロイが走ります。**GitHub Actions でワークフローが成功したこととロールアウト完了を確認**してください。失敗時や再実行が必要な場合は、同ワークフローの **workflow_dispatch**（手動実行）も利用できます。

その後、GitHub で `feature/payment-decimal-discount` → `main` の PR を再作成してください。

> **`fix/payment-division-by-zero`:** `main` を force reset すると、`fix` の先端は **マージ済みの古い v1.2 コミット**を指したままになり、次回の「fix → main の PR」が成立しないことがあります。次回デモ前に **下記「リポジトリのメンテナンス順序（推奨）」** または `./scripts/refresh-demo-branches.sh` で `feature` / `fix` を再整列してください。

---

## OTel リソース属性

| 属性 | 値 | 設定場所 |
|------|-----|---------|
| `service.name` | `order-service` / `payment-service` | k8s deployment env `OTEL_SERVICE_NAME` |
| `deployment.environment` | `agentic-o11y` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.version` | `1.0` / `1.1` / `1.2` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
| `service.namespace` | `agentic-o11y-mcp` | k8s deployment env `OTEL_RESOURCE_ATTRIBUTES` |
