#!/usr/bin/env bash
# Box side of a hotelmercury.jp redeploy: swap the docroot for /tmp/hm-dist.tar.
# Staged + run by deploy/push.sh; needs sudo: sudo bash /tmp/hm-redeploy.sh <sha256>
set -Eeuo pipefail
umask 022
U=hotelmercury; D=hotelmercury.jp; TAR=/tmp/hm-dist.tar
DOC="/home/$U/web/$D/public_html"
echo "$1  $TAR" | sha256sum -c -
[[ -d "$DOC" ]] || { echo "docroot $DOC missing"; exit 1; }
find "$DOC" -mindepth 1 -delete
tar -xf "$TAR" -C "$DOC"
chown -R "$U:$U" "$DOC"
find "$DOC" -type d -exec chmod 755 {} +
find "$DOC" -type f -exec chmod 644 {} +
rm -f "$TAR"
for p in / /robots.txt /sitemap.xml; do
  printf '%-14s %s\n' "$p" "$(curl -sk -o /dev/null -w '%{http_code}' --resolve "$D:443:5.104.81.60" "https://$D$p")"
done
echo "Deployed. HTML is DYNAMIC at Cloudflare; css/js are ?v=-versioned. Changed images need a purge."
