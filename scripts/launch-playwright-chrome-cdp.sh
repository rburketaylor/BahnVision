#!/usr/bin/env bash
#
# Launch Playwright's Chromium binary with Chrome DevTools Protocol (CDP) enabled
# This allows you to connect external tools or scripts via CDP on port 9222
#

set -euo pipefail

# Configuration
CDP_PORT="${CDP_PORT:-9222}"
USER_DATA_DIR="${USER_DATA_DIR:-/tmp/playwright-chrome-cdp-profile}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Launching Playwright Chromium with CDP...${NC}"

# Find the Playwright Chromium binary
CHROME_PATH=$(find ~/.cache/ms-playwright -name "chrome" -type f -executable 2>/dev/null | grep chromium | head -n 1)

if [ -z "$CHROME_PATH" ]; then
    echo -e "${RED}❌ Error: Playwright Chromium binary not found.${NC}"
    echo "Please make sure Playwright browsers are installed:"
    echo "  cd frontend && npx playwright install chromium"
    exit 1
fi

echo -e "${GREEN}✓ Found Chromium binary at:${NC} $CHROME_PATH"
echo -e "${GREEN}✓ CDP endpoint will be available at:${NC} http://localhost:$CDP_PORT"
echo -e "${GREEN}✓ WebSocket endpoint will be shown when Chrome launches${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop Chrome${NC}"
echo ""

# Launch Chrome with CDP enabled
exec "$CHROME_PATH" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$USER_DATA_DIR" \
    --no-first-run \
    --no-default-browser-check \
    "$@"
