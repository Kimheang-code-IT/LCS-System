#!/bin/sh
# First-deploy TLS bootstrap for a clean Docker host (Hostinger VPS, EC2, ...).
#
# The production nginx config loads /etc/letsencrypt/live/<domain>/fullchain.pem,
# so a brand-new host cannot start the stack until that certificate exists.
# This helper issues it into the exact named volume the stack mounts, then the
# Production workflow can deploy normally.
#
# Usage (on the host, DNS already pointing at it, port 80 free):
#   ./bootstrap-host.sh --domain lcslog.minidev.in --email admin@example.com
#
# Optional:
#   --deploy-dir /opt/lcs                     runtime directory to prepare
#   --volume freight_forwarding_certbot_etc   named volume holding /etc/letsencrypt
#   --force                                   re-issue even if a certificate exists
#
# It is idempotent: with a certificate already present it does nothing.
set -eu

DOMAIN=""
EMAIL=""
DEPLOY_DIR="/opt/lcs"
CERT_VOLUME="freight_forwarding_certbot_etc"
FORCE="false"

usage() {
    cat <<'EOF'
Usage: bootstrap-host.sh --domain <hostname> --email <address> [options]

  --domain <hostname>   Public hostname the certificate is issued for
  --email <address>     ACME account / expiry contact
  --deploy-dir <path>   Runtime directory to create (default /opt/lcs)
  --volume <name>       Docker volume for /etc/letsencrypt
                        (default freight_forwarding_certbot_etc)
  --force               Issue a new certificate even if one already exists
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --domain) DOMAIN=$2; shift 2 ;;
        --email) EMAIL=$2; shift 2 ;;
        --deploy-dir) DEPLOY_DIR=$2; shift 2 ;;
        --volume) CERT_VOLUME=$2; shift 2 ;;
        --force) FORCE="true"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Both --domain and --email are required." >&2
    usage >&2
    exit 2
fi

if docker info >/dev/null 2>&1; then
    DOCKER="docker"
elif sudo -n docker info >/dev/null 2>&1; then
    DOCKER="sudo -E docker"
else
    echo "Docker is not usable by this user (install it, or run with sudo)." >&2
    exit 1
fi

# 1. Runtime directory owned by the deploy user, writable by the workflow.
if [ "$DOCKER" = "docker" ]; then
    mkdir -p "$DEPLOY_DIR/nginx"
else
    sudo -n mkdir -p "$DEPLOY_DIR/nginx"
    sudo -n chown -R "$(id -u):$(id -g)" "$DEPLOY_DIR"
fi
echo "Runtime directory ready: $DEPLOY_DIR"

# 2. DNS check. A mismatch is a warning, not a stop: split-horizon DNS and a
#    proxy in front of the host are both legitimate.
PUBLIC_IP="$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)"
RESOLVED="$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1; exit}' || true)"
if [ -z "$RESOLVED" ]; then
    echo "WARNING: $DOMAIN does not resolve yet; the ACME challenge will fail." >&2
elif [ -n "$PUBLIC_IP" ] && [ "$RESOLVED" != "$PUBLIC_IP" ]; then
    echo "WARNING: $DOMAIN resolves to $RESOLVED but this host is $PUBLIC_IP." >&2
fi
echo "DNS: $DOMAIN -> ${RESOLVED:-unresolved}"

# 3. Already issued? Nothing to do.
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if $DOCKER run --rm -v "$CERT_VOLUME:/etc/letsencrypt" alpine:3.20 \
       test -f "$CERT_PATH" >/dev/null 2>&1; then
    if [ "$FORCE" != "true" ]; then
        echo "Certificate for $DOMAIN already exists in $CERT_VOLUME; nothing to do."
        exit 0
    fi
    echo "Re-issuing certificate for $DOMAIN (--force)."
fi

# 4. Port 80 must be free for the standalone challenge.
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ':80 '; then
    echo "Port 80 is already in use. Stop the stack first:" >&2
    echo "  cd $DEPLOY_DIR && docker compose -f docker-compose.prod.yml stop frontend" >&2
    exit 1
fi

# 5. Issue with the standalone authenticator into the stack's cert volume.
echo "Requesting certificate for $DOMAIN via Let's Encrypt..."
$DOCKER run --rm -p 80:80 \
    -v "$CERT_VOLUME:/etc/letsencrypt" \
    certbot/certbot certonly --standalone \
    -d "$DOMAIN" \
    --email "$EMAIL" --agree-tos --no-eff-email --non-interactive

# 6. Verify the exact files nginx mounts.
if ! $DOCKER run --rm -v "$CERT_VOLUME:/etc/letsencrypt" alpine:3.20 \
        test -f "$CERT_PATH" >/dev/null 2>&1; then
    echo "Certificate issue reported success but $CERT_PATH is missing." >&2
    exit 1
fi
echo "Certificate ready: $CERT_VOLUME:$CERT_PATH"
echo "Next: run the Production workflow (workflow_dispatch) for the first deploy."
