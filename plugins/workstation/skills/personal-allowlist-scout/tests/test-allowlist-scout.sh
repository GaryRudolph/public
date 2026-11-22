#!/usr/bin/env bash
# Render-then-scan tests for the allowlist scout. Needs only python3.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
exec python3 -I "$here/test_render_scan.py"
