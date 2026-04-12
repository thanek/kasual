#!/usr/bin/env bash
# Wyodrębnia napisy i18n z kodu Python, aktualizuje pliki .ts
# i kompiluje je do binarnych .qm.
#
# Użycie:
#   ./update_translations.sh          – aktualizuje wszystkie języki
#   ./update_translations.sh en       – tylko angielski
#
# Wymagania: pylupdate6, lrelease (pakiet qt6-tools lub pyqt6-dev-tools)

set -euo pipefail
cd "$(dirname "$0")"

LANGUAGES=("pl" "en")

if [[ $# -gt 0 ]]; then
    LANGUAGES=("$@")
fi

SRC_FILES=$(find src -name "*.py" | sort | tr '\n' ' ')

echo "── Wyodrębnianie napisów z kodu źródłowego ──────────────────────────────"
for lang in "${LANGUAGES[@]}"; do
    ts="locale/kasual_${lang}.ts"
    echo "  pylupdate6 → ${ts}"
    # shellcheck disable=SC2086
    pylupdate6 $SRC_FILES -ts "$ts"
done

echo
echo "── Kompilowanie .ts → .qm ───────────────────────────────────────────────"
for lang in "${LANGUAGES[@]}"; do
    ts="locale/kasual_${lang}.ts"
    if [[ -f "$ts" ]]; then
        echo "  lrelease  → locale/kasual_${lang}.qm"
        lrelease "$ts" -qm "locale/kasual_${lang}.qm"
    fi
done

echo
echo "Gotowe."
