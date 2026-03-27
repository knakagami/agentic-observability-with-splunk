#!/usr/bin/env bash
# refresh-demo-branches.sh — demo 用 feature/fix を v1.0 ベースラインに追従させる
#
# demo-reset 後、main は v1.0 だが feature/fix は古いマージ履歴を指したままになりうる。
# このスクリプトは origin/demo/v1.0-base を各ブランチに取り込み、次回 PR を切りやすくする。
#
# 使い方:
#   ./scripts/refresh-demo-branches.sh           # ドライラン（実行するコマンドを表示）
#   ./scripts/refresh-demo-branches.sh --apply   # 実際に merge を実行（コンフリクト時は手解決）
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

FEATURE_BRANCH="feature/payment-decimal-discount"
FIX_BRANCH="fix/payment-division-by-zero"
BASE_REF="origin/demo/v1.0-base"

APPLY=false
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=true
fi

echo ">>> git fetch origin"
git fetch origin

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "Error: $BASE_REF not found. Push demo/v1.0-base first." >&2
  exit 1
fi

echo ""
echo "=== Commits on $FEATURE_BRANCH not in $BASE_REF (first 15) ==="
git log --oneline "$BASE_REF..origin/$FEATURE_BRANCH" 2>/dev/null | head -15 || true
echo ""
echo "=== Commits on $FIX_BRANCH not in origin/$FEATURE_BRANCH (first 15) ==="
git log --oneline "origin/$FEATURE_BRANCH..origin/$FIX_BRANCH" 2>/dev/null | head -15 || true

echo ""
echo "=== 推奨: baseline を feature / fix にマージ ==="
echo "git checkout $FEATURE_BRANCH && git merge $BASE_REF -m \"chore: merge demo/v1.0-base into $FEATURE_BRANCH\""
echo "git checkout $FIX_BRANCH && git merge $BASE_REF -m \"chore: merge demo/v1.0-base into $FIX_BRANCH\""
echo ""
echo "=== 代替（履歴を畳みたい場合）: baseline から作り直し + cherry-pick ==="
echo "# git checkout -B $FEATURE_BRANCH $BASE_REF"
echo "# git cherry-pick <v1.1 を導入するコミットの SHA>   # git log $BASE_REF..origin/$FEATURE_BRANCH で確認"
echo "# git checkout -B $FIX_BRANCH $FEATURE_BRANCH"
echo "# git cherry-pick <v1.2 修正コミットの SHA>"
echo "# git push -f origin $FEATURE_BRANCH $FIX_BRANCH   # 共有ブランチなら事前合意を"

if [[ "$APPLY" != true ]]; then
  echo ""
  echo "(ドライラン終了。実行するには: $0 --apply)"
  exit 0
fi

echo ""
echo ">>> Applying merges into local branches..."

git checkout "$FEATURE_BRANCH"
git merge "$BASE_REF" -m "chore: merge demo/v1.0-base into $FEATURE_BRANCH"

git checkout "$FIX_BRANCH"
git merge "$BASE_REF" -m "chore: merge demo/v1.0-base into $FIX_BRANCH"

echo ""
echo "✅ ローカルでマージ完了。リモートへ反映:"
echo "   git push origin $FEATURE_BRANCH"
echo "   git push origin $FIX_BRANCH"
