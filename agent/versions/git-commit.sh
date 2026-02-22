#!/bin/bash
# CITARION Git Auto-Commit Tool
# Автоматический коммит изменений

set -e

PROJECT_ROOT="/home/z/my-project"
VERSIONS_DIR="$PROJECT_ROOT/.agent/versions"
JOURNAL_FILE="$VERSIONS_DIR/journal.json"
INDEX_FILE="$VERSIONS_DIR/index.json"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Инициализация git если нужно
init_git() {
    cd "$PROJECT_ROOT"
    if [ ! -d ".git" ]; then
        log_info "Initializing git repository..."
        git init
        git config user.email "agent@citarion.local"
        git config user.name "CITARION Agent"
        
        # Создаём .gitignore
        cat > .gitignore << 'EOF'
node_modules/
.next/
download/
*.lock
db/*.db
.env*
!.env.example
EOF
        log_info "Git repository initialized"
    fi
}

# Проверка есть ли изменения
has_changes() {
    cd "$PROJECT_ROOT"
    [ -n "$(git status --porcelain)" ]
}

# Создание коммита
make_commit() {
    local message="$1"
    local type="${2:-chore}"
    
    cd "$PROJECT_ROOT"
    
    # Добавляем все отслеживаемые файлы
    git add src/ docs/ prisma/ .agent/ *.md *.json *.yaml *.ts 2>/dev/null || true
    
    # Создаём коммит
    git commit -m "[$type] $message" --allow-empty-message
    
    local commit_hash=$(git rev-parse HEAD)
    log_info "Commit created: $commit_hash"
    
    # Обновляем индекс
    if [ -f "$INDEX_FILE" ]; then
        TMP_FILE=$(mktemp)
        jq --arg hash "$commit_hash" \
           --arg timestamp "$(date -Iseconds)" \
           --arg message "$message" \
           '.git.last_commit = $timestamp | .git.last_commit_hash = $hash | .git.commits_count += 1' \
           "$INDEX_FILE" > "$TMP_FILE" && mv "$TMP_FILE" "$INDEX_FILE"
    fi
    
    echo "$commit_hash"
}

# Главная логика
main() {
    local action="${1:-auto}"
    local message="${2:-Automated commit}"
    local type="${3:-chore}"
    
    case "$action" in
        init)
            init_git
            ;;
        auto)
            init_git
            if has_changes; then
                log_info "Changes detected, creating commit..."
                make_commit "$message" "$type"
            else
                log_info "No changes to commit"
            fi
            ;;
        force)
            init_git
            make_commit "$message" "$type"
            ;;
        status)
            cd "$PROJECT_ROOT"
            git status
            ;;
        log)
            cd "$PROJECT_ROOT"
            git log --oneline -10
            ;;
        *)
            echo "Usage: $0 [init|auto|force|status|log] [message] [type]"
            echo ""
            echo "Actions:"
            echo "  init   - Initialize git repository"
            echo "  auto   - Auto commit if changes exist (default)"
            echo "  force  - Force commit even if empty"
            echo "  status - Show git status"
            echo "  log    - Show recent commits"
            echo ""
            echo "Types: feat, fix, docs, style, refactor, test, chore"
            exit 1
            ;;
    esac
}

main "$@"
