# SPL Queries — Splunk Observability Demo

These queries are used during the agentic demo when Claude searches for the root cause
of the payment-service error spike via the Splunk MCP.

---

## 1. エラーログの確認 — 直近5分のエラー件数

```spl
index=demo_logs sourcetype="demo:app"
  level=ERROR
  earliest=-5m
| stats count BY service.name, message
| sort -count
```

---

## 2. スタックトレース抽出 — ZeroDivisionError の発見

```spl
index=demo_logs sourcetype="demo:app"
  level=ERROR
  earliest=-15m
| search message="*ZeroDivisionError*" OR message="*division by zero*" OR message="*decimal_part*"
| table _time, trace_id, span_id, service.name, message
| sort -_time
```

---

## 3. trace_id によるトレース ↔ ログ相関

```spl
index=demo_logs sourcetype="demo:app"
  trace_id=<TRACE_ID_FROM_O11Y>
| table _time, service.name, level, message, span_id
| sort _time
```

---

## 4. 整数金額のみが失敗していることを証明 (Ah-Ha Moment)

```spl
index=demo_logs sourcetype="demo:app"
  earliest=-15m
| eval amount_is_integer=if(round(amount,0)==amount, "integer", "decimal")
| stats
    count AS total,
    sum(eval(if(level="ERROR",1,0))) AS errors
  BY amount_is_integer
| eval error_rate=round(errors/total*100, 1)
| table amount_is_integer, total, errors, error_rate
```

期待される結果:
| amount_is_integer | total | errors | error_rate |
|-------------------|-------|--------|-----------|
| integer           | ~60   | ~60    | ~100.0    |
| decimal           | ~40   | 0      | 0.0       |

---

## 5. エラー率の時系列 (デプロイ前後の比較)

```spl
index=demo_logs sourcetype="demo:app"
  earliest=-30m
| bin _time span=1m
| stats
    count AS total,
    sum(eval(if(level="ERROR",1,0))) AS errors
  BY _time, "service.name"
| eval error_rate_pct=round(errors/total*100, 1)
| where "service.name"="payment-service"
| table _time, total, errors, error_rate_pct
```

---

## 6. 回復確認 — v1.2 デプロイ後のエラー率 0%

```spl
index=demo_logs sourcetype="demo:app"
  "service.name"=payment-service
  earliest=-5m
| stats
    count AS total,
    sum(eval(if(level="ERROR",1,0))) AS errors
  BY "service.name"
| eval error_rate=round(errors/total*100, 1)
| table "service.name", total, errors, error_rate
```

---

## 備考

- `trace_id` フィールドは OTel SDK が自動付与し、JSON ログに埋め込まれる
- Splunk Observability Cloud のトレース画面の trace_id をコピーして Query 3 に使うと
  そのトレースに対応するアプリケーションログを即座に確認できる
- Query 4 は「整数金額のみが失敗」というバグパターンを統計的に証明する
  デモのクライマックス (Ah-Ha Moment) となるクエリ
