#!/bin/sh
set -eu
marker=/run/lab-netlock/ready
rm -f "$marker"
iptables -P OUTPUT DROP
iptables -C OUTPUT -o lo -j ACCEPT 2>/dev/null || iptables -I OUTPUT 1 -o lo -j ACCEPT
ipv6_enabled() { [ "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6 2>/dev/null || echo 0)" != "1" ]; }
if ipv6_enabled; then
  command -v ip6tables-restore >/dev/null
  ip6tables -P OUTPUT DROP
  ip6tables -C OUTPUT -o lo -j ACCEPT 2>/dev/null || ip6tables -I OUTPUT 1 -o lo -j ACCEPT
fi
apply_rules() {
  # Resolve peers while the previous complete ruleset is still installed.
  {
    printf '*filter\n:INPUT ACCEPT [0:0]\n:FORWARD DROP [0:0]\n:OUTPUT DROP [0:0]\n'
    printf '%s\n' '-A OUTPUT -o lo -j ACCEPT' '-A OUTPUT -d 127.0.0.11 -p udp --dport 53 -j ACCEPT' '-A OUTPUT -d 127.0.0.11 -p tcp --dport 53 -j ACCEPT' '-A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT'
    for spec in 'academy 8000' 'target 9090' 'receiver 8081' 'mailpit 8025' 'ollama 11434'; do
      set -- $spec
      host=$1; port=$2
      for ip in $(getent ahostsv4 "$host" 2>/dev/null | awk '{print $1}' | sort -u); do
        printf '%s\n' "-A OUTPUT -d $ip -p tcp --dport $port -j ACCEPT"
      done
    done
    printf '%s\n' '-A OUTPUT -j REJECT' 'COMMIT'
  } > /tmp/kali-egress.v4
  iptables-restore < /tmp/kali-egress.v4
  if ipv6_enabled; then
    printf '%s\n' '*filter' ':INPUT ACCEPT [0:0]' ':FORWARD DROP [0:0]' ':OUTPUT DROP [0:0]' '-A OUTPUT -o lo -j ACCEPT' '-A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT' '-A OUTPUT -j REJECT' 'COMMIT' > /tmp/kali-egress.v6
    ip6tables-restore < /tmp/kali-egress.v6
  fi
  printf '%s\n' "$(readlink /proc/self/ns/net)" > "$marker.tmp"
  chmod 0644 "$marker.tmp"
  mv "$marker.tmp" "$marker"
}
apply_rules
while sleep 10; do apply_rules; done
