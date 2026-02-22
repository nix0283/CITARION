#!/bin/bash
# CITARION Snapshot Tool
# Создаёт snapshot файлов проекта

set -e

PROJECT_ROOT="/home/z/my-project"
VERSIONS_DIR="$PROJECT_ROOT/.agent/versions"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
DATE=$(date +%Y-%m-%d)
HOUR=$(date +%H)

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Тип snapshot: daily, hourly, before-change
SNAPSHOT_TYPE="${1:-daily}"

case "$SNAPSHOT_TYPE" in
    daily)
        SNAPSHOT_DIR="$VERSIONS_DIR/daily/$DATE"
        ;;
    hourly)
        SNAPSHOT_DIR="$VERSIONS_DIR/hourly/$DATE/$HOUR"
        ;;
    before-change)
        SNAPSHOT_DIR="$VERSIONS_DIR/before-change/$TIMESTAMP"
        ;;
    *)
        log_error "Unknown snapshot type: $SNAPSHOT_TYPE"
        echo "Usage: $0 [daily|hourly|before-change]"
        exit 1
        ;;
esac

# Создаём директорию
mkdir -p "$SNAPSHOT_DIR"

log_info "Creating $SNAPSHOT_TYPE snapshot: $SNAPSHOT_DIR"

# Копируем отслеживаемые директории
copy_dir() {
    local src="$1"
    local dest="$2"
    if [ -d "$src" ]; then
        mkdir -p "$dest"
        cp -r "$src" "$dest/" 2>/dev/null || true
        log_info "Copied: $src"
    fi
}

# Копируем ключевые директории (ИСКЛЮЧАЯ .agent/versions для избежания рекурсии)
copy_dir "$PROJECT_ROOT/src" "$SNAPSHOT_DIR/src"
copy_dir "$PROJECT_ROOT/docs" "$SNAPSHOT_DIR/docs"
copy_dir "$PROJECT_ROOT/prisma" "$SNAPSHOT_DIR/prisma"

# Копируем .agent БЕЗ versions (используем rsync для исключения)
mkdir -p "$SNAPSHOT_DIR/.agent"
rsync -a --exclude='versions' "$PROJECT_ROOT/.agent/" "$SNAPSHOT_DIR/.agent/" 2>/dev/null || true
log_info "Copied: .agent (excluding versions)"

# Копируем корневые файлы
mkdir -p "$SNAPSHOT_DIR/root"
cp "$PROJECT_ROOT"/*.md "$SNAPSHOT_DIR/root/" 2>/dev/null || true
cp "$PROJECT_ROOT"/*.json "$SNAPSHOT_DIR/root/" 2>/dev/null || true
cp "$PROJECT_ROOT"/*.yaml "$SNAPSHOT_DIR/root/" 2>/dev/null || true
cp "$PROJECT_ROOT"/*.ts "$SNAPSHOT_DIR/root/" 2>/dev/null || true

# Создаём манифест
MANIFEST_FILE="$SNAPSHOT_DIR/manifest.json"
cat > "$MANIFEST_FILE" << EOF
{
  "snapshot_type": "$SNAPSHOT_TYPE",
  "created_at": "$(date -Iseconds)",
  "timestamp": "$TIMESTAMP",
  "project_root": "$PROJECT_ROOT",
  "files_count": $(find "$SNAPSHOT_DIR" -type f | wc -l),
  "total_size_bytes": $(du -sb "$SNAPSHOT_DIR" | cut -f1)
}
EOF

log_info "Snapshot created: $SNAPSHOT_DIR"
log_info "Files: $(find "$SNAPSHOT_DIR" -type f | wc -l)"

# Обновляем индекс
INDEX_FILE="$VERSIONS_DIR/index.json"
if [ -f "$INDEX_FILE" ]; then
    # Добавляем запись о snapshot в индекс (через временный файл)
    TMP_FILE=$(mktemp)
    jq --arg type "$SNAPSHOT_TYPE" \
       --arg path "$SNAPSHOT_DIR" \
       --arg timestamp "$(date -Iseconds)" \
       '.snapshots[$type] += [{"path": $path, "timestamp": $timestamp}]' \
       "$INDEX_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$INDEX_FILE"
fi

echo "$SNAPSHOT_DIR"
