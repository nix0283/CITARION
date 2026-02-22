#!/bin/bash
# CITARION Rollback Tool
# Откат к предыдущей версии

set -e

PROJECT_ROOT="/home/z/my-project"
VERSIONS_DIR="$PROJECT_ROOT/.agent/versions"
JOURNAL_FILE="$VERSIONS_DIR/journal.json"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Показать доступные snapshot'ы
list_snapshots() {
    echo "=== Daily Snapshots ==="
    ls -la "$VERSIONS_DIR/daily/" 2>/dev/null || echo "None"
    
    echo ""
    echo "=== Hourly Snapshots (last 5) ==="
    find "$VERSIONS_DIR/hourly" -type d -name "[0-9]*" 2>/dev/null | tail -5 || echo "None"
    
    echo ""
    echo "=== Before-Change Snapshots (last 10) ==="
    ls -lt "$VERSIONS_DIR/before-change/" 2>/dev/null | head -10 || echo "None"
}

# Показать git историю
list_git_commits() {
    cd "$PROJECT_ROOT"
    if [ -d ".git" ]; then
        echo "=== Recent Git Commits ==="
        git log --oneline -10
    else
        log_warn "Git not initialized"
    fi
}

# Откат к snapshot
rollback_to_snapshot() {
    local snapshot_path="$1"
    
    if [ ! -d "$snapshot_path" ]; then
        log_error "Snapshot not found: $snapshot_path"
        exit 1
    fi
    
    log_warn "This will OVERWRITE current files!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
    
    # Создаём backup текущего состояния
    log_step "Creating backup of current state..."
    "$VERSIONS_DIR/snapshot.sh" before-change
    
    # Восстанавливаем файлы
    log_step "Restoring files from snapshot..."
    
    if [ -d "$snapshot_path/src" ]; then
        rm -rf "$PROJECT_ROOT/src"
        cp -r "$snapshot_path/src" "$PROJECT_ROOT/"
        log_info "Restored: src/"
    fi
    
    if [ -d "$snapshot_path/docs" ]; then
        rm -rf "$PROJECT_ROOT/docs"
        cp -r "$snapshot_path/docs" "$PROJECT_ROOT/"
        log_info "Restored: docs/"
    fi
    
    if [ -d "$snapshot_path/prisma" ]; then
        rm -rf "$PROJECT_ROOT/prisma"
        cp -r "$snapshot_path/prisma" "$PROJECT_ROOT/"
        log_info "Restored: prisma/"
    fi
    
    if [ -d "$snapshot_path/.agent" ]; then
        rm -rf "$PROJECT_ROOT/.agent"
        cp -r "$snapshot_path/.agent" "$PROJECT_ROOT/"
        log_info "Restored: .agent/"
    fi
    
    if [ -d "$snapshot_path/root" ]; then
        cp "$snapshot_path/root"/* "$PROJECT_ROOT/" 2>/dev/null || true
        log_info "Restored: root files"
    fi
    
    log_info "Rollback completed!"
}

# Откат к git commit
rollback_to_commit() {
    local commit_hash="$1"
    
    cd "$PROJECT_ROOT"
    
    if [ ! -d ".git" ]; then
        log_error "Git not initialized"
        exit 1
    fi
    
    log_warn "This will RESET to commit: $commit_hash"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
    
    # Создаём backup
    log_step "Creating backup..."
    "$VERSIONS_DIR/snapshot.sh" before-change
    
    # Reset к коммиту
    git reset --hard "$commit_hash"
    
    log_info "Rolled back to: $commit_hash"
}

# Главная логика
main() {
    local action="${1:-list}"
    
    case "$action" in
        list)
            list_snapshots
            echo ""
            list_git_commits
            ;;
        snapshot)
            rollback_to_snapshot "$2"
            ;;
        commit)
            rollback_to_commit "$2"
            ;;
        journal)
            # Показать последние записи журнала
            echo "=== Recent Journal Entries ==="
            jq '.entries[-5:]' "$JOURNAL_FILE" 2>/dev/null || echo "Journal not found"
            ;;
        *)
            echo "Usage: $0 [list|snapshot <path>|commit <hash>|journal]"
            echo ""
            echo "Actions:"
            echo "  list              - Show available snapshots and commits"
            echo "  snapshot <path>   - Rollback to snapshot"
            echo "  commit <hash>     - Rollback to git commit"
            echo "  journal           - Show recent journal entries"
            exit 1
            ;;
    esac
}

main "$@"
