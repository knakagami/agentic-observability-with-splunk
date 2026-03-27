# SPL Queries — Splunk Observability Demo

These queries are used during the agentic demo when Claude searches for the root cause
of the payment-service error spike via the Splunk MCP.

**環境に合わせる:** インデックスは **`index=agentic-o11y-demo`**、デプロイは **`deployment.environment=agentic-o11y`**。時間窓はデモでは **5〜15 分**（例 `earliest=-10m`）を推奨。

**ベース絞り込み（コピー用）:**

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-10m
(sourcetype=kube:container:payment-service OR sourcetype=kube:container:order-service OR sourcetype=kube:container:load-generator)
```

---

## 1. KeyError の件数・生ログ

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-10m
sourcetype=kube:container:payment-service KeyError
| stats count
```

---

## 2. payment の処理ログ（amount・trace_id）

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-10m
sourcetype=kube:container:payment-service "Processing payment"
| head 50
```

（`_raw` が JSON の場合は `spath` や `rex` で `amount` / `trace_id` を取り出すことも可）

---

## 3. trace_id によるトレース ↔ ログ相関

O11y のトレース画面から `trace_id` をコピーして `<TRACE_ID>` に貼り付ける。

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-15m
<TRACE_ID>
| table _time, sourcetype, _raw
| sort _time
```

---

## 4. load-generator: is_integer × status_code（502 の有無）

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-15m
sourcetype=kube:container:load-generator "Request sent"
| stats count BY is_integer, status_code
```

---

## 5. KeyError の時系列（1 分粒度）

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-15m
sourcetype=kube:container:payment-service KeyError
| timechart span=1m count
```

---

## 6. 回復確認 — payment-service の KeyError が近いゼロか

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-10m
sourcetype=kube:container:payment-service KeyError
| stats count
```

---

## 7. load-generator: クライアント失敗（KeyError 以外）

`Request failed` ログには `error_class`・`retry_count` が付く（接続・タイムアウト等の切り分け用）。

```spl
index=agentic-o11y-demo deployment.environment=agentic-o11y earliest=-15m
sourcetype=kube:container:load-generator "Request failed"
| stats count BY error_class
```

---

## 備考

- JSON ログの `trace_id` は Splunk Observability Cloud のトレース ID と相関できる（Query 3）。
- 旧プレースホルダ `index=demo_logs` / `sourcetype="demo:app"` は本番デモ環境では使わない。
- 整数金額パターンの詳細は payment の `amount` ログと load-generator の `is_integer` を併用すると説明しやすい。
