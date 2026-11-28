#!/bin/sh
dir=${0%/*}
[ "$dir" = "$0" ] && dir=.
dir=$(CDPATH= cd -- "$dir" && pwd) || exit 0
[ -f "$dir/devin_gate.py" ] || exit 0
export FE_ARCH_ROOT=$(CDPATH= cd -- "$dir/.." && pwd) || exit 0
# PATH can be minimal when the host app launches from Finder, so look in the usual places too.
# Probe the interpreter before exec: a Windows Store alias exists but exits 9009.
for candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 7))' >/dev/null 2>&1; then
    exec "$candidate" "$dir/devin_gate.py"
  fi
done
exit 0
