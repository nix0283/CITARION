# CITARION Version Control System

Гибридная система версионности: **Git + Snapshot + Journal**

## Структура

```
.agent/versions/
├── journal.json           # Журнал всех изменений (D)
├── index.json             # Индекс версий
├── version_manager.py     # Python менеджер
├── snapshot.sh            # Скрипт snapshot'ов (B)
├── git-commit.sh          # Git automation (A)
├── rollback.sh            # Откат версий
├── daily/                 # Ежедневные snapshot'ы
│   └── 2025-01-17/
├── hourly/                # Ежечасные snapshot'ы
│   └── 2025-01-17/12/
├── before-change/         # Snapshot'ы перед изменениями
│   └── 2025-01-17_12-30-00/
└── snapshots/             # Дополнительные snapshot'ы
```

## Использование

### Python API (рекомендуется)

```python
from version_manager import VersionManager

vm = VersionManager()

# Создать snapshot
vm.create_snapshot("daily")          # Ежедневный
vm.create_snapshot("hourly")         # Ежечасный
vm.create_snapshot("before-change")  # Перед изменением

# Git commit
vm.git_commit("Добавлен новый компонент", "feat")

# Добавить запись в журнал
vm.add_journal_entry("Исправлен баг", ["src/app/page.tsx"])

# Статус
vm.print_status()
```

### Shell скрипты

```bash
# Snapshot
./.agent/versions/snapshot.sh daily
./.agent/versions/snapshot.sh hourly
./.agent/versions/snapshot.sh before-change

# Git
./.agent/versions/git-commit.sh auto "message" "feat"
./.agent/versions/git-commit.sh status
./.agent/versions/git-commit.sh log

# Rollback
./.agent/versions/rollback.sh list
./.agent/versions/rollback.sh snapshot .agent/versions/daily/2025-01-17
./.agent/versions/rollback.sh commit abc123
```

### CLI

```bash
# Python CLI
python .agent/versions/version_manager.py snapshot daily
python .agent/versions/version_manager.py commit "message" feat
python .agent/versions/version_manager.py journal add "description" --files file1.ts file2.ts
python .agent/versions/version_manager.py status
```

## Компоненты

### A. Git Automation

- Автоматическая инициализация git
- Автоматические коммиты с типами (feat, fix, docs, chore)
- Конфигурация .gitignore
- История коммитов

### B. Snapshot Backups

- **daily**: Полный snapshot раз в день
- **hourly**: Snapshot каждый час
- **before-change**: Snapshot перед каждым изменением

### D. Change Journal

- JSON журнал всех изменений
- Timestamp, тип, описание
- Связь с snapshot и git commit
- Возможность отката

## Workflow

### При начале работы

```python
# 1. Проверить статус
vm.print_status()

# 2. Создать snapshot перед изменениями
vm.create_snapshot("before-change")
```

### После изменений

```python
# 1. Добавить запись в журнал
vm.add_journal_entry("Описание изменений", ["file1.ts", "file2.ts"])

# 2. Создать git commit
vm.git_commit("Описание изменений", "feat")
```

### Для отката

```bash
# 1. Посмотреть доступные версии
./.agent/versions/rollback.sh list

# 2. Откатиться к snapshot или commit
./.agent/versions/rollback.sh snapshot <path>
./.agent/versions/rollback.sh commit <hash>
```

## Интеграция с агентом

При начале новой сессии агент должен:

1. Прочитать `journal.json` для понимания последних изменений
2. Проверить `status()` для текущего состояния
3. Создать `before-change` snapshot перед критическими изменениями
4. Добавлять записи в журнал при каждом изменении

## Конфигурация

В `journal.json`:

```json
{
  "config": {
    "max_daily_snapshots": 30,
    "max_hourly_snapshots": 24,
    "max_before_change_snapshots": 50,
    "auto_git_commit": true,
    "snapshot_before_change": true
  }
}
```

## Очистка старых версий

```bash
# Удалить snapshot'ы старше 30 дней
find .agent/versions/daily -mtime +30 -exec rm -rf {} +
find .agent/versions/hourly -mtime +7 -exec rm -rf {} +
find .agent/versions/before-change -mtime +1 -exec rm -rf {} +
```
