#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# run_tests.sh — Run the full JobXplore test suite
#
# Usage:
#   ./scripts/run_tests.sh            # run all tests
#   ./scripts/run_tests.sh api        # API tests only (Docker)
#   ./scripts/run_tests.sh extension  # Chrome extension tests only
#   ./scripts/run_tests.sh web        # Web app tests only
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

run_api_tests() {
  echo "━━━ API Tests (Python / pytest) ━━━"
  docker build \
    -f "$REPO_ROOT/docker/Dockerfile.api.test" \
    -t jobxplore-api-test \
    "$REPO_ROOT"
  docker run --rm \
    -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
    -e SUPABASE_JWT_SECRET="test-secret" \
    -e ENCRYPTION_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1wYWQ=" \
    jobxplore-api-test
}

run_extension_tests() {
  echo "━━━ Extension Tests (vitest) ━━━"
  cd "$REPO_ROOT/apps/extension"
  npm install --silent
  npm test
}

run_web_tests() {
  echo "━━━ Web Tests (vitest) ━━━"
  cd "$REPO_ROOT/apps/web"
  npm install --silent
  npm test
}

case "$TARGET" in
  api)
    run_api_tests
    ;;
  extension)
    run_extension_tests
    ;;
  web)
    run_web_tests
    ;;
  all)
    run_api_tests
    echo ""
    run_extension_tests
    echo ""
    run_web_tests
    echo ""
    echo "✓ All tests passed"
    ;;
  *)
    echo "Unknown target: $TARGET. Use: api | extension | web | all"
    exit 1
    ;;
esac
