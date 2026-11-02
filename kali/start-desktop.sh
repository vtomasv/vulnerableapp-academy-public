#!/bin/sh
set -eu
# Xvfb/noVNC necesita un framebuffer X11 estable, sin composición GLX.
# Esto cambia únicamente el XFCE de Kali, nunca el escritorio del anfitrión.
xfconf-query -c xfwm4 -p /general/use_compositing -s false 2>/dev/null || \
  xfconf-query -c xfwm4 -p /general/use_compositing --create --type bool --set false
exec /usr/bin/startxfce4
