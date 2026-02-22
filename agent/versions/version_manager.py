#!/usr/bin/env python3
"""
CITARION Version Control Manager
Гибридная система версионности: Git + Snapshot + Journal

Использование:
    python version_manager.py snapshot [daily|hourly|before-change]
    python version_manager.py commit "message" [type]
    python version_manager.py journal add "description" ["file1" "file2"]
    python version_manager.py status
    python version_manager.py rollback snapshot <path>
    python version_manager.py rollback commit <hash>
"""

import json
import hashlib
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import argparse


class VersionManager:
    """Менеджер версионности CITARION"""
    
    def __init__(self, project_root: str = "/home/z/my-project"):
        self.project_root = Path(project_root)
        self.versions_dir = self.project_root / ".agent" / "versions"
        self.journal_file = self.versions_dir / "journal.json"
        self.index_file = self.versions_dir / "index.json"
        
        # Создаём директории если нужно
        for subdir in ["daily", "hourly", "before-change", "snapshots"]:
            (self.versions_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        # Инициализируем файлы если нужно
        self._init_files()
    
    def _init_files(self):
        """Инициализация файлов журнала и индекса"""
        if not self.journal_file.exists():
            self._write_json(self.journal_file, {
                "version": "1.0.0",
                "created": datetime.now().isoformat(),
                "entries": [],
                "statistics": {
                    "total_changes": 0,
                    "total_snapshots": 0
                }
            })
        
        if not self.index_file.exists():
            self._write_json(self.index_file, {
                "version": "1.0.0",
                "last_updated": datetime.now().isoformat(),
                "git": {"initialized": False, "commits_count": 0},
                "snapshots": {"daily": [], "hourly": [], "before_change": []},
                "tracked_files": {}
            })
    
    def _read_json(self, path: Path) -> Dict:
        """Чтение JSON файла"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write_json(self, path: Path, data: Dict):
        """Запись JSON файла"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Получение хеша файла"""
        if not file_path.exists():
            return ""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _get_tracked_files(self) -> List[Path]:
        """Получение списка отслеживаемых файлов"""
        patterns = [
            "src/**/*.ts", "src/**/*.tsx",
            "docs/**/*.md",
            "prisma/**/*",
            ".agent/**/*",
            "*.md", "*.json", "*.yaml"
        ]
        
        files = []
        for pattern in patterns:
            if pattern.startswith("*"):
                # Корневые файлы
                files.extend(self.project_root.glob(pattern))
            else:
                files.extend(self.project_root.glob(pattern))
        
        # Фильтруем игнорируемые (включая versions для избежания рекурсии)
        ignore = ["node_modules", ".next", "download", "db", "versions"]
        return [f for f in files if not any(x in str(f) for x in ignore)]
    
    # === SNAPSHOT METHODS ===
    
    def create_snapshot(self, snapshot_type: str = "daily") -> str:
        """Создание snapshot'а"""
        timestamp = datetime.now()
        
        if snapshot_type == "daily":
            snapshot_dir = self.versions_dir / "daily" / timestamp.strftime("%Y-%m-%d")
        elif snapshot_type == "hourly":
            snapshot_dir = self.versions_dir / "hourly" / timestamp.strftime("%Y-%m-%d") / timestamp.strftime("%H")
        elif snapshot_type == "before-change":
            snapshot_dir = self.versions_dir / "before-change" / timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        else:
            raise ValueError(f"Unknown snapshot type: {snapshot_type}")
        
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Копируем директории (с исключением versions для .agent)
        for dirname in ["src", "docs", "prisma"]:
            src = self.project_root / dirname
            if src.exists():
                dst = snapshot_dir / dirname
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        
        # Копируем .agent БЕЗ versions (во избежание рекурсии)
        agent_src = self.project_root / ".agent"
        if agent_src.exists():
            agent_dst = snapshot_dir / ".agent"
            if agent_dst.exists():
                shutil.rmtree(agent_dst)
            shutil.copytree(agent_src, agent_dst, ignore=shutil.ignore_patterns('versions'))
        
        # Копируем корневые файлы
        root_dir = snapshot_dir / "root"
        root_dir.mkdir(exist_ok=True)
        for ext in ["*.md", "*.json", "*.yaml", "*.ts"]:
            for f in self.project_root.glob(ext):
                if f.is_file():
                    shutil.copy2(f, root_dir / f.name)
        
        # Создаём манифест
        manifest = {
            "snapshot_type": snapshot_type,
            "created_at": timestamp.isoformat(),
            "files_count": sum(1 for _ in snapshot_dir.rglob("*") if _.is_file()),
            "total_size": sum(f.stat().st_size for f in snapshot_dir.rglob("*") if f.is_file())
        }
        self._write_json(snapshot_dir / "manifest.json", manifest)
        
        # Обновляем индекс
        self._update_index_snapshot(snapshot_type, str(snapshot_dir), timestamp.isoformat())
        
        # Добавляем запись в журнал
        self._add_journal_entry(
            entry_type="snapshot",
            description=f"Created {snapshot_type} snapshot",
            files_affected=[],
            snapshot_path=str(snapshot_dir)
        )
        
        return str(snapshot_dir)
    
    def _update_index_snapshot(self, snapshot_type: str, path: str, timestamp: str):
        """Обновление индекса snapshot'ами"""
        index = self._read_json(self.index_file)
        key = snapshot_type.replace("-", "_")
        index["snapshots"][key].append({
            "path": path,
            "timestamp": timestamp
        })
        index["last_updated"] = datetime.now().isoformat()
        self._write_json(self.index_file, index)
    
    # === JOURNAL METHODS ===
    
    def _add_journal_entry(self, entry_type: str, description: str, 
                           files_affected: List[str], snapshot_path: str = None,
                           git_commit: str = None) -> str:
        """Добавление записи в журнал"""
        journal = self._read_json(self.journal_file)
        
        entry_id = f"entry-{len(journal['entries']) + 1:04d}"
        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "description": description,
            "files_affected": files_affected,
            "snapshot_path": snapshot_path,
            "git_commit": git_commit,
            "rollback_available": snapshot_path is not None or git_commit is not None
        }
        
        journal["entries"].append(entry)
        journal["statistics"]["total_changes"] += 1
        if snapshot_path:
            journal["statistics"]["total_snapshots"] += 1
        
        self._write_json(self.journal_file, journal)
        return entry_id
    
    def add_journal_entry(self, description: str, files: List[str] = None) -> str:
        """Публичный метод добавления записи"""
        # Создаём snapshot перед изменением
        snapshot_path = self.create_snapshot("before-change")
        
        return self._add_journal_entry(
            entry_type="change",
            description=description,
            files_affected=files or [],
            snapshot_path=snapshot_path
        )
    
    # === GIT METHODS ===
    
    def git_init(self) -> bool:
        """Инициализация git репозитория"""
        git_dir = self.project_root / ".git"
        if git_dir.exists():
            return True
        
        # Создаём .gitignore
        gitignore = self.project_root / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text("""node_modules/
.next/
download/
*.lock
db/*.db
.env*
!.env.example
""")
        
        # Инициализируем git
        subprocess.run(["git", "init"], cwd=self.project_root, check=True)
        subprocess.run(["git", "config", "user.email", "agent@citarion.local"], 
                      cwd=self.project_root, check=True)
        subprocess.run(["git", "config", "user.name", "CITARION Agent"], 
                      cwd=self.project_root, check=True)
        
        # Обновляем индекс
        index = self._read_json(self.index_file)
        index["git"]["initialized"] = True
        self._write_json(self.index_file, index)
        
        return True
    
    def git_commit(self, message: str, commit_type: str = "chore") -> Optional[str]:
        """Создание git коммита"""
        self.git_init()
        
        # Проверяем есть ли изменения
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        if not result.stdout.strip():
            return None
        
        # Добавляем файлы
        for dirname in ["src", "docs", "prisma", ".agent"]:
            subprocess.run(["git", "add", dirname], cwd=self.project_root)
        for ext in ["*.md", "*.json", "*.yaml"]:
            subprocess.run(["git", "add", ext], cwd=self.project_root, shell=False)
        
        # Коммитим
        full_message = f"[{commit_type}] {message}"
        subprocess.run(["git", "commit", "-m", full_message], 
                      cwd=self.project_root, check=True)
        
        # Получаем хеш коммита
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        commit_hash = result.stdout.strip()
        
        # Обновляем индекс
        index = self._read_json(self.index_file)
        index["git"]["last_commit"] = datetime.now().isoformat()
        index["git"]["last_commit_hash"] = commit_hash
        index["git"]["commits_count"] += 1
        self._write_json(self.index_file, index)
        
        # Добавляем в журнал
        self._add_journal_entry(
            entry_type="git_commit",
            description=full_message,
            files_affected=[],
            git_commit=commit_hash
        )
        
        return commit_hash
    
    # === STATUS ===
    
    def status(self) -> Dict:
        """Получение статуса версионности"""
        index = self._read_json(self.index_file)
        journal = self._read_json(self.journal_file)
        
        # Проверяем git статус
        git_status = "not_initialized"
        has_changes = False
        if (self.project_root / ".git").exists():
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            git_status = "clean" if not result.stdout.strip() else "dirty"
            has_changes = bool(result.stdout.strip())
        
        return {
            "git": {
                "status": git_status,
                "has_changes": has_changes,
                "commits_count": index["git"]["commits_count"]
            },
            "snapshots": {
                "daily_count": len(index["snapshots"]["daily"]),
                "hourly_count": len(index["snapshots"]["hourly"]),
                "before_change_count": len(index["snapshots"]["before_change"])
            },
            "journal": {
                "entries_count": len(journal["entries"]),
                "total_changes": journal["statistics"]["total_changes"]
            }
        }
    
    def print_status(self):
        """Вывод статуса в консоль"""
        status = self.status()
        
        print("=== CITARION Version Control Status ===\n")
        
        print(f"Git: {status['git']['status']}")
        if status['git']['has_changes']:
            print("  ⚠️  Uncommitted changes")
        print(f"  Commits: {status['git']['commits_count']}")
        
        print(f"\nSnapshots:")
        print(f"  Daily: {status['snapshots']['daily_count']}")
        print(f"  Hourly: {status['snapshots']['hourly_count']}")
        print(f"  Before-change: {status['snapshots']['before_change_count']}")
        
        print(f"\nJournal:")
        print(f"  Entries: {status['journal']['entries_count']}")
        print(f"  Total changes: {status['journal']['total_changes']}")


def main():
    parser = argparse.ArgumentParser(description="CITARION Version Control Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # snapshot command
    snap_parser = subparsers.add_parser("snapshot", help="Create snapshot")
    snap_parser.add_argument("type", nargs="?", default="daily", 
                            choices=["daily", "hourly", "before-change"],
                            help="Snapshot type")
    
    # commit command
    commit_parser = subparsers.add_parser("commit", help="Create git commit")
    commit_parser.add_argument("message", help="Commit message")
    commit_parser.add_argument("type", nargs="?", default="chore",
                              choices=["feat", "fix", "docs", "style", "refactor", "test", "chore"],
                              help="Commit type")
    
    # journal command
    journal_parser = subparsers.add_parser("journal", help="Journal operations")
    journal_parser.add_argument("action", choices=["add", "list"],
                               help="Journal action")
    journal_parser.add_argument("description", nargs="?", help="Entry description")
    journal_parser.add_argument("--files", nargs="*", help="Affected files")
    
    # status command
    subparsers.add_parser("status", help="Show version control status")
    
    args = parser.parse_args()
    vm = VersionManager()
    
    if args.command == "snapshot":
        path = vm.create_snapshot(args.type)
        print(f"Snapshot created: {path}")
    
    elif args.command == "commit":
        commit_hash = vm.git_commit(args.message, args.type)
        if commit_hash:
            print(f"Commit created: {commit_hash}")
        else:
            print("No changes to commit")
    
    elif args.command == "journal":
        if args.action == "add":
            entry_id = vm.add_journal_entry(args.description, args.files)
            print(f"Journal entry created: {entry_id}")
        elif args.action == "list":
            journal = vm._read_json(vm.journal_file)
            for entry in journal["entries"][-10:]:
                print(f"[{entry['timestamp']}] {entry['type']}: {entry['description']}")
    
    elif args.command == "status":
        vm.print_status()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
