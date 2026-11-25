#!/usr/bin/env bash
# Construit l'AppImage et le paquet .deb (exécuté par GitHub Actions sur Ubuntu 22.04).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import jcfportable; print(jcfportable.VERSION)")
ARCH=x86_64
rm -rf build dist out
mkdir -p out

# 1) Application autonome (Python + Qt embarqués : rien à installer sur le PC)
pyinstaller --noconfirm --clean --windowed --name jcfportable --paths . \
  --add-data "jcfportable/icon.png:jcfportable" \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore \
  packaging/run.py
APP=dist/jcfportable

# Bibliothèque nécessaire à Qt 6 sur certaines Linux Mint
cp -L /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0 "$APP/_internal/" || true

# 2) AppImage avec Hamlib embarqué (rigctld + rigctl)
APPDIR=build/AppDir
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/hamlib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -a "$APP" "$APPDIR/usr/lib/jcfportable"
for tool in rigctld rigctl; do
  cp -L "/usr/bin/$tool" "$APPDIR/usr/bin/"
  ldd "/usr/bin/$tool" | awk '/=> \//{print $3}' | while read -r lib; do
    case "$(basename "$lib")" in
      libc.so*|libm.so*|libpthread.so*|libdl.so*|librt.so*|ld-linux*|libstdc++.so*|libgcc_s.so*) ;;
      *) cp -Ln "$lib" "$APPDIR/usr/lib/hamlib/" ;;
    esac
  done
  patchelf --set-rpath '$ORIGIN/../lib/hamlib' "$APPDIR/usr/bin/$tool"
done
for lib in "$APPDIR"/usr/lib/hamlib/*.so*; do patchelf --set-rpath '$ORIGIN' "$lib" || true; done
cp packaging/jcfportable.desktop "$APPDIR/"
cp packaging/jcfportable.desktop "$APPDIR/usr/share/applications/"
cp packaging/jcfportable.svg "$APPDIR/jcfportable.svg"
cp packaging/jcfportable.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${APPDIR:-$HERE}"
exec "$HERE/usr/lib/jcfportable/jcfportable" "$@"
EOF
chmod +x "$APPDIR/AppRun"
if [ ! -x build/appimagetool ]; then
  wget -q -O build/appimagetool \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x build/appimagetool
fi
ARCH=$ARCH build/appimagetool --appimage-extract-and-run "$APPDIR" "out/JCFPortable-$VERSION-$ARCH.AppImage"

# 3) Paquet .deb (installe Hamlib automatiquement via ses dépendances)
DEB=build/deb
mkdir -p "$DEB/DEBIAN" "$DEB/opt" "$DEB/usr/bin" "$DEB/usr/share/applications" \
         "$DEB/usr/share/icons/hicolor/scalable/apps"
cp -a "$APP" "$DEB/opt/jcfportable"
ln -s /opt/jcfportable/jcfportable "$DEB/usr/bin/jcfportable"
cp packaging/jcfportable.desktop "$DEB/usr/share/applications/"
cp packaging/jcfportable.svg "$DEB/usr/share/icons/hicolor/scalable/apps/"
SIZE=$(du -sk "$DEB" | cut -f1)
cat > "$DEB/DEBIAN/control" <<EOF
Package: jcfportable
Version: $VERSION
Section: hamradio
Priority: optional
Architecture: amd64
Depends: libhamlib-utils, libxcb-cursor0, libegl1, libxkbcommon-x11-0
Installed-Size: $SIZE
Maintainer: F4JCF
Homepage: https://github.com/F4JCF/jcfportable
Description: Carnet d'activation portable POTA, WWFF, SOTA, GMA, WWBOTA
 Logiciel de saisie rapide des QSO en activation portable, inspiré de
 Ham2K PoLo : spots, self-spot, CAT Hamlib, exports ADIF par référence.
EOF
cat > "$DEB/DEBIAN/postinst" <<'EOF'
#!/bin/sh
# Autorise l'accès aux ports série (CAT) pour l'utilisateur qui installe
if [ -n "$SUDO_USER" ] && getent group dialout >/dev/null; then
  usermod -a -G dialout "$SUDO_USER" || true
fi
command -v update-desktop-database >/dev/null && update-desktop-database -q || true
exit 0
EOF
chmod 755 "$DEB/DEBIAN/postinst"
dpkg-deb --root-owner-group --build "$DEB" "out/jcfportable_${VERSION}_amd64.deb"
ls -lh out
