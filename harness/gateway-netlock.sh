#!/bin/sh
set -eu
# Este proceso comparte únicamente el namespace de red del gateway.
# No publica puertos ni recibe instrucciones del modelo.
apply_rules() {
    iptables -P OUTPUT DROP
    iptables -F OUTPUT
    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    for pair in academy:8000 kali:6080 mailpit:8025; do
        host=${pair%:*}
        port=${pair#*:}
        for ip in $(getent ahostsv4 "$host" | awk '{print $1}' | sort -u); do
            iptables -A OUTPUT -d "$ip" -p tcp --dport "$port" -j ACCEPT
        done
    done
    iptables -A OUTPUT -j REJECT
    # IPv6 está deshabilitado por sysctl en el dueño del namespace.
    test "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" = 1
}
while :; do
    apply_rules
    sleep 10
done
