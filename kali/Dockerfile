FROM node:24-bookworm AS harness-builder

ARG PENTEST_HARNESS_COMMIT=4638f38082bdf37cea03ad151905c4bb8662f6e9
ENV CI=1 LEFTHOOK=0 DSH_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends git python3 make g++ \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global pnpm@11.7.0
WORKDIR /build/pentest-harness
RUN git init . \
    && git remote add origin https://github.com/S1N6H/pentest-harness.git \
    && git fetch --depth 1 origin "${PENTEST_HARNESS_COMMIT}" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${PENTEST_HARNESS_COMMIT}"
RUN pnpm install --frozen-lockfile && pnpm run build:official

FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       chromium \
       curl \
       dbus-x11 \
       default-jdk \
       firefox-esr \
       git \
       iproute2 \
       iptables \
       jq \
       ldap-utils \
       less \
       nano \
       netcat-openbsd \
       novnc \
       nmap \
       openssl \
       python3 \
       python3-flask \
       python3-pycryptodome \
       python3-requests \
       python3-venv \
       sqlmap \
       supervisor \
       xfce4 \
       xfce4-terminal \
       x11vnc \
       x11-xserver-utils \
       xvfb \
       websockify \
       zaproxy \
       zip \
       unzip \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash kali \
    && useradd --create-home --uid 1001 --shell /usr/sbin/nologin runner \
    && mkdir -p /run/lab-netlock /run/academy-secrets /var/lib/kali-progress /home/kali/.config/va-lab \
    && chown -R kali:kali /home/kali /var/lib/kali-progress \
    && chown -R runner:runner /home/runner

RUN python3 -m venv /opt/playwright-venv \
    && /opt/playwright-venv/bin/pip install --no-cache-dir 'playwright==1.64.1'

# Capas estables: fuente original y dependencias compiladas, antes del material docente.
COPY --from=harness-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=harness-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=harness-builder /build/pentest-harness /opt/pentest-harness
RUN mkdir -p /opt/academy-harness \
    && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s ../lib/node_modules/pnpm/bin/pnpm.cjs /usr/local/bin/pnpm \
    && ln -s /opt/pentest-harness/apps/cli/node_modules /opt/academy-harness/node_modules \
    && test -s /opt/pentest-harness/apps/cli/lib/bin.js

COPY kali/entrypoint.sh /usr/local/bin/kali-entrypoint.sh
COPY kali/runner.py /usr/local/bin/runner.py
COPY kali/lab.py /usr/local/bin/lab
COPY kali/solve_crypto.py /usr/local/bin/lab-crypto
COPY kali/supervisord.conf /etc/supervisor/conf.d/va-lab.conf
COPY kali/desktop/ /opt/academy-desktop/
COPY docs/ /opt/vulnerableapp-academy/docs/
COPY harness/ /opt/academy-harness/
COPY harness/presets/vulnerableapp/ /opt/pentest-harness/apps/cli/config/agent-presets/vulnerableapp/
COPY academy/data/catalog.json /opt/academy-harness/catalog.json
COPY harness/tools.py /usr/local/bin/lab-harness-tools
RUN chmod 0755 /usr/local/bin/kali-entrypoint.sh /usr/local/bin/runner.py /usr/local/bin/lab /usr/local/bin/lab-crypto \
    /usr/local/bin/lab-harness-tools /opt/academy-harness/start.sh \
    && chmod 0644 /etc/supervisor/conf.d/va-lab.conf \
    && node --check /opt/academy-harness/workshop-plugin.mjs \
    && python3 -m py_compile /opt/academy-harness/ollama_proxy.py \
    && test -s /opt/pentest-harness/apps/cli/config/agent-presets/vulnerableapp/agent.cordis.yml \
    && python3 -c 'import os; p="/usr/lib/nmap/nmap"; "security.capability" in os.listxattr(p) and os.removexattr(p, "security.capability")'

ENV PATH="/opt/playwright-venv/bin:${PATH}" \
    HOME=/home/kali \
    DISPLAY=:99 \
    DSH_HOME=/home/kali/.local/share/pentest-harness \
    DSH_TELEMETRY_DISABLED=1 \
    OLLAMA_DUMMY_API_KEY=ollama-local-only

EXPOSE 6080 9001
ENTRYPOINT ["/usr/local/bin/kali-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/va-lab.conf"]
