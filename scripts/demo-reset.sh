#!/bin/bash
# demo-reset.sh — デモ環境を v1.0 ベースラインにリセットする
#
# 使い方:
#   ./scripts/demo-reset.sh
#
# 前提:
#   - リモートにブランチ demo/v1.0-base が存在すること
#     （README の手順: git push origin main:demo/v1.0-base 等で作成・更新）
#
# デモ終了後の手順:
#   1. ./scripts/demo-reset.sh を実行
#   2. GitHub で feature/payment-decimal-discount → main の PR を再作成

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
echo "次のデモに向けて、以下の PR を GitHub で再作成してください:"
echo "  feature/payment-decimal-discount → main  (v1.1 バグ導入 PR)"
echo ""
echo "  fix/payment-division-by-zero は Claude が GitHub MCP でデモ中に作成します"
