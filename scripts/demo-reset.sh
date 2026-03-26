#!/bin/bash
# demo-reset.sh — デモ環境を v1.0 ベースラインにリセットする
#
# 使い方:
#   ./scripts/demo-reset.sh
#
# 前提:
#   - v1.0-demo-base タグが存在すること
#     （cleanup PR を main にマージした後、初回のみ以下を実行）
#     git tag v1.0-demo-base origin/main
#     git push origin v1.0-demo-base
#
# デモ終了後の手順:
#   1. ./scripts/demo-reset.sh を実行
#   2. GitHub で feature/payment-decimal-discount → main の PR を再作成

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "🔄 main を v1.0-demo-base にリセット中..."
git fetch origin
git checkout main
git reset --hard v1.0-demo-base
git push -f origin main

echo ""
echo "✅ リセット完了: main → v1.0"
echo ""
echo "次のステップ:"
echo "  1. GitHub Actions で「Build and Deploy」が起動していることを確認し、成功まで待つ"
echo "     （push -f で main が更新されたため自動起動。再実行は workflow_dispatch でも可）"
echo ""
echo "次のデモに向けて、以下の PR を GitHub で再作成してください:"
echo "  feature/payment-decimal-discount → main  (v1.1 バグ導入 PR)"
echo ""
echo "  fix/payment-division-by-zero はデモ中に GitHub MCP でマージする想定です"
