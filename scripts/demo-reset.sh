#!/bin/bash
# demo-reset.sh — デモ環境を v1.0 ベースラインにリセットする
#
# 使い方:
#   ./scripts/demo-reset.sh
#
# 前提:
#   - リモートにブランチ demo/v1.0-base が存在すること
#     （README の手順: main が v1.0 のときに git push origin main:demo/v1.0-base 等で作成・更新）
#
# デモ終了後の手順:
#   1. ./scripts/demo-reset.sh を実行
#   2. GitHub Actions の成功を確認
#   3. GitHub で feature/payment-decimal-discount → main の PR を再作成
#   4. （推奨）scripts/refresh-demo-branches.sh で feature/fix を基点から再整列

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "🔄 main を origin/demo/v1.0-base にリセット中..."
git fetch origin
git checkout main
git reset --hard origin/demo/v1.0-base
git push -f origin main

echo ""
echo "✅ リセット完了: main → v1.0 (demo/v1.0-base と同一コミット)"
echo ""
echo "次のステップ:"
echo "  1. GitHub Actions で「Build and Deploy」が起動していることを確認し、成功まで待つ"
echo "     （push -f で main が更新されたため自動起動。再実行は workflow_dispatch でも可）"
echo ""
echo "次のデモに向けて:"
echo "  - GitHub で feature/payment-decimal-discount → main の PR を再作成（v1.1 導入）"
echo "  - fix/payment-division-by-zero は reset 後も古い履歴を指しうるため、"
echo "    ./scripts/refresh-demo-branches.sh で再整列するか README のメンテ手順に従う"
