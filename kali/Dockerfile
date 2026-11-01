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

COPY kali/entrypoint.sh /usr/local/bin/kali-entrypoint.sh
COPY kali/runner.py /usr/local/bin/runner.py
COPY kali/lab.py /usr/local/bin/lab
COPY kali/solve_crypto.py /usr/local/bin/lab-crypto
COPY kali/supervisord.conf /etc/supervisor/conf.d/va-lab.conf
COPY kali/desktop/ /opt/academy-desktop/
COPY docs/ /opt/vulnerableapp-academy/docs/

RUN chmod 0755 /usr/local/bin/kali-entrypoint.sh /usr/local/bin/runner.py /usr/local/bin/lab /usr/local/bin/lab-crypto \
    && chmod 0644 /etc/supervisor/conf.d/va-lab.conf

ENV PATH="/opt/playwright-venv/bin:${PATH}" \
    HOME=/home/kali \
    DISPLAY=:99

EXPOSE 6080 9001
ENTRYPOINT ["/usr/local/bin/kali-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/va-lab.conf"]
