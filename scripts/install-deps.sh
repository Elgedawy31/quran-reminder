#!/bin/sh
# Install system packages only. Run install.sh separately as your normal user.
set -eu
if [ ! -f /etc/os-release ]; then
    echo 'Cannot detect the distribution. See README.md for manual dependencies.' >&2
    exit 1
fi
. /etc/os-release
elevate() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo 'Install these packages as root:' >&2
        printf '%s ' "$@" >&2
        printf '\n' >&2
        exit 1
    fi
}
case " $ID ${ID_LIKE:-} " in
    *' debian '*|*' ubuntu '*)
        elevate apt-get update
        elevate apt-get install git python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 librsvg2-common fonts-noto-core
        ;;
    *' fedora '*)
        elevate dnf install git python3 python3-gobject python3-cairo gtk3 gtk-layer-shell google-noto-sans-arabic-fonts google-noto-naskh-arabic-fonts
        ;;
    *' arch '*|*' manjaro '*)
        # Full upgrade avoids partial upgrades on Arch.
        elevate pacman -Syu --needed git python python-gobject python-cairo gtk3 gtk-layer-shell noto-fonts
        ;;
    *)
        echo "No automatic package recipe for $ID. Install Python 3.10+, PyGObject, PyCairo, GTK3 and Noto Arabic fonts." >&2
        echo 'Wayland desktops other than GNOME also need GTK Layer Shell. A systemd user session is required.' >&2
        exit 1
        ;;
esac
