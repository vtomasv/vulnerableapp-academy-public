#!/bin/sh
set -eu
command -v docker >/dev/null 2>&1 || { echo 'Docker no está en PATH' >&2; exit 2; }
docker compose config --quiet
docker compose up -d --build

i=0
until docker compose exec -T kali sh -c 'curl -fsS --max-time 3 http://academy:8000/health >/dev/null && curl -fsS --max-time 3 http://target:9090/VulnerableApp/ >/dev/null && curl -fsS --max-time 3 http://127.0.0.1:6080/vnc.html >/dev/null && nc -z 127.0.0.1 5900'; do
  i=$((i+1)); [ "$i" -lt 180 ] || { docker compose ps; exit 1; }; sleep 2
done

docker compose exec -T --user kali kali lab doctor
docker compose exec -T kali curl -fsS --max-time 5 http://ollama:11434/api/tags
docker compose exec -T lab-netlock iptables -C OUTPUT -j REJECT
docker compose exec -T lab-netlock sh -c 'iptables -S OUTPUT | grep -q -- "-P OUTPUT DROP"'
docker compose exec -T target-netlock iptables -C OUTPUT -j REJECT

if docker compose exec -T --user kali kali curl --noproxy '*' --connect-timeout 3 --max-time 5 -fsS http://1.1.1.1/ >/dev/null 2>&1; then
  echo 'ERROR: Kali alcanzó un destino externo' >&2; exit 1
fi

container=$(docker compose ps -q kali)
gateways=$(docker inspect "$container" --format '{{range .NetworkSettings.Networks}}{{.Gateway}} {{end}}')
for ip in $gateways; do
  if docker compose exec -T --user kali kali curl --noproxy '*' --connect-timeout 2 --max-time 3 -fsS "http://$ip/" >/dev/null 2>&1; then
    echo 'ERROR: Kali alcanzó un servicio HTTP en el gateway del host' >&2; exit 1
  fi
done

echo 'Comprobaciones terminadas: servicios internos, escritorio, modelo y reglas OUTPUT DROP.'
echo 'Una conexión fallida sola no prueba aislamiento absoluto: revisar firewall, DNS, motor y políticas del anfitrión.'
