#!/bin/bash
# switch-version.sh — payment-serviceのバージョンを切り替えてデプロイ
#
# 使い方:
#   ./scripts/switch-version.sh v1.0   # 正常版にリセット
#   ./scripts/switch-version.sh v1.1   # バグ版 (ZeroDivisionError)
#   ./scripts/switch-version.sh v1.2   # 修正版

set -e

VERSION=$1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <version>"
  echo "  version: v1.0 | v1.1 | v1.2"
  exit 1
}

[ -z "$VERSION" ] && usage

case "$VERSION" in
  v1.0)
    SRC="$REPO_ROOT/services/payment-service/main_v1.0_normal.py"
    VER_NUM="1.0"
    LABEL="v1.0 (正常版)"
    ;;
  v1.1)
    SRC="$REPO_ROOT/services/payment-service/main_v1.1_bug.py"
    VER_NUM="1.1"
    LABEL="v1.1 (バグあり: ZeroDivisionError)"
    ;;
  v1.2)
    SRC="$REPO_ROOT/services/payment-service/main_v1.2_fix.py"
    VER_NUM="1.2"
    LABEL="v1.2 (修正済み)"
    ;;
  *)
    echo "Error: unknown version '$VERSION'"
    usage
    ;;
esac

if [ ! -f "$SRC" ]; then
  echo "Error: source file not found: $SRC"
  exit 1
fi

cd "$REPO_ROOT"

# main.py を差し替え
cp "$SRC" services/payment-service/main.py
echo "✓ services/payment-service/main.py → $LABEL"

# deployment.yaml の service.version を更新
sed -i "s/service\.version=[0-9]\+\.[0-9]\+/service.version=${VER_NUM}/" \
  k8s/payment-service/deployment.yaml
echo "✓ k8s/payment-service/deployment.yaml → service.version=${VER_NUM}"

# git commit & push
git add services/payment-service/main.py k8s/payment-service/deployment.yaml
git commit -m "demo: switch payment-service to ${VERSION}"
git push origin main

echo ""
echo "Deployed: $LABEL"
echo "GitHub Actions will build and deploy to K3s automatically."
