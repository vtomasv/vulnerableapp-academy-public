#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo 'Kali entrypoint must start as root so supervisord can drop to uid 1000/1001' >&2
    exit 1
fi

marker=/run/lab-netlock/ready
# Let the resident sidecar remove a marker left by a prior named-volume generation.
sleep 1
rm -f "$marker"
i=0
while [ ! -s "$marker" ]; do
    i=$((i + 1))
    if [ "$i" -ge 120 ]; then
        echo 'Kali network lock did not become ready' >&2
        exit 1
    fi
    sleep 1
done
expected_namespace=$(readlink /proc/self/ns/net)
actual_namespace=$(cat "$marker")
[ "$actual_namespace" = "$expected_namespace" ] || {
    echo 'Kali network lock marker belongs to another namespace' >&2
    exit 1
}

[ -r /run/academy-secrets/harness.key ] || {
    echo 'runner secret is not available' >&2
    exit 1
}

# The init service normally owns this volume already; this is safe and idempotent
# for a pre-existing volume and uses only the minimal CHOWN-related capabilities.
chown -R 1000:1000 /home/kali 2>/dev/null || true
mkdir -p /home/kali/.config/va-lab
chown -R 1000:1000 /home/kali/.config 2>/dev/null || true
mkdir -p /home/kali/Desktop
cp -n /opt/academy-desktop/* /home/kali/Desktop/ 2>/dev/null || true
chmod +x /home/kali/Desktop/*.desktop 2>/dev/null || true
chown -R 1000:1000 /home/kali/Desktop 2>/dev/null || true

exec "$@"
