#!/usr/bin/env bash
# Reports what is already serving the web on this box, so the API gets added
# to it rather than fighting it. Read-only - changes nothing.
echo "=== listening on 80 / 443 ==="
(ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep -E ':(80|443)\s' || echo "  nothing"

echo
echo "=== web servers installed ==="
for p in nginx apache2 httpd caddy; do
    if command -v "$p" >/dev/null 2>&1; then
        printf '  %-8s %s\n' "$p" "$("$p" -v 2>&1 | head -1)"
    fi
done
command -v docker >/dev/null 2>&1 && echo "  docker   $(docker --version)"

echo
echo "=== active vhosts ==="
[ -d /etc/nginx/sites-enabled ] && ls /etc/nginx/sites-enabled/ 2>/dev/null | sed 's/^/  nginx: /'
[ -d /etc/nginx/conf.d ] && ls /etc/nginx/conf.d/*.conf 2>/dev/null | sed 's/^/  nginx: /'
[ -d /etc/apache2/sites-enabled ] && ls /etc/apache2/sites-enabled/ 2>/dev/null | sed 's/^/  apache: /'
[ -f /etc/caddy/Caddyfile ] && grep -E '^[a-z0-9.*-]+\s*\{' /etc/caddy/Caddyfile 2>/dev/null | sed 's/^/  caddy: /'

echo
echo "=== containers ==="
docker ps --format '  {{.Names}}  {{.Ports}}' 2>/dev/null || echo "  none / no access"

echo
echo "=== existing certificates ==="
ls /etc/letsencrypt/live/ 2>/dev/null | sed 's/^/  /' || echo "  none found"

echo
echo "=== free memory / load ==="
free -h | sed -n 2p | sed 's/^/  /'
uptime | sed 's/^/  /'
