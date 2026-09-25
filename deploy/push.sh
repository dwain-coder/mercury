#!/usr/bin/env bash
# Local side (Git Bash, not PowerShell - it corrupts the piped tar): release build,
# upload, then print the one sudo command to run on the box.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python tests/test_hm.py
python build.py --release
tar -cf /tmp/hm-dist.tar -C dist .
sha=$(sha256sum /tmp/hm-dist.tar | cut -d' ' -f1)
ssh admin@5.104.81.60 "cat > /tmp/hm-dist.tar" < /tmp/hm-dist.tar
ssh admin@5.104.81.60 "cat > /tmp/hm-redeploy.sh" < deploy/box-redeploy.sh
rm -f /tmp/hm-dist.tar
echo "On the box:  sudo bash /tmp/hm-redeploy.sh $sha"
