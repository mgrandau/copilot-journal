#!/usr/bin/env python3
"""Installation script for Copilot Journal instruction files.

Installs journaling instructions to local repos or global VS Code config
so GitHub Copilot automatically captures design decisions, reasoning,
and context as you code.

Usage:
    CLI: `copilot-journal [--global] [--insiders] [--dry-run]`
    Programmatic: `installer = create_installer(); installer.install_local()`
"""

import argparse
import logging
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

__all__ = [
    "create_installer",
    "setup_logging",
    "main",
    "AgentInstaller",
    "InstallationResult",
    "FileMapping",
    "PathResolver",
    "EditorDetector",
    "OperatingSystem",
    "FileSystemProtocol",
    "EnvironmentProtocol",
    "RealFileSystem",
    "RealEnvironment",
]

_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class OperatingSystem(Enum):
    WINDOWS = "Windows"
    DARWIN = "Darwin"
    LINUX = "Linux"


class FileSystemProtocol(Protocol):
    def exists(self, path: Path) -> bool: ...
    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None: ...
    def copy_file(self, src: Path, dst: Path) -> None: ...
    def get_cwd(self) -> Path: ...


class EnvironmentProtocol(Protocol):
    def get_system(self) -> str: ...
    def get_env_var(self, name: str, default: str = "") -> str: ...
    def get_home(self) -> Path: ...


class RealFileSystem:
    def exists(self, path: Path) -> bool:  # pragma: no cover
        return path.exists()

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:  # pragma: no cover
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def copy_file(self, src: Path, dst: Path) -> None:  # pragma: no cover
        shutil.copy2(src, dst)

    def get_cwd(self) -> Path:  # pragma: no cover
        return Path.cwd()


class RealEnvironment:
    def get_system(self) -> str:  # pragma: no cover
        return platform.system()

    def get_env_var(self, name: str, default: str = "") -> str:  # pragma: no cover
        return os.environ.get(name, default)

    def get_home(self) -> Path:  # pragma: no cover
        return Path.home()


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    logger_name: str = "copilot_journal",
) -> logging.Logger:
    valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    level_upper = level.upper()
    if level_upper not in valid_levels:
        raise ValueError(f"Invalid log level '{level}'. Must be one of: {', '.join(valid_levels)}")

    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level_upper))
    logger.handlers.clear()

    formatter = logging.Formatter(fmt="%(message)s", datefmt=_LOG_DATE_FORMAT)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt=_LOG_DATE_FORMAT,
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


@dataclass(frozen=True, slots=True)
class FileMapping:
    src_relative: str
    dst_relative: str


@dataclass(frozen=True, slots=True)
class InstallationResult:
    success: bool
    files_copied: int
    target_dir: Path
    error_message: str | None = None
    files_failed: int = 0


class PathResolver:
    EDITOR_PATHS: dict[OperatingSystem, dict[str, list[str]]] = {
        OperatingSystem.WINDOWS: {
            "Code": ["Code", "User"],
            "Code-Insiders": ["Code - Insiders", "User"],
        },
        OperatingSystem.LINUX: {
            "Code": [".config", "Code", "User"],
            "Code-Insiders": [".config", "Code - Insiders", "User"],
        },
        OperatingSystem.DARWIN: {
            "Code": ["Library", "Application Support", "Code", "User"],
            "Code-Insiders": ["Library", "Application Support", "Code - Insiders", "User"],
        },
    }

    def __init__(self, env: EnvironmentProtocol, fs: FileSystemProtocol):
        self.env = env
        self.fs = fs
        system_str = env.get_system()
        try:
            self.system = OperatingSystem(system_str)
        except ValueError:
            raise ValueError(f"Unsupported operating system: {system_str}") from None

    def get_vscode_config_dir(self, editor: str) -> Path | None:
        if editor not in self.EDITOR_PATHS[self.system]:
            return None

        path_parts = self.EDITOR_PATHS[self.system][editor]

        if self.system == OperatingSystem.WINDOWS:
            appdata = self.env.get_env_var("APPDATA")
            if not appdata:
                return None
            base = Path(appdata)
        else:
            base = self.env.get_home()

        result = base
        for part in path_parts:
            result = result / part
        return result

    def get_local_install_dir(self) -> Path:
        current = self.fs.get_cwd()
        while current.parent != current:
            if self.fs.exists(current / ".git"):
                return current / ".github"
            current = current.parent
        return self.fs.get_cwd() / ".github"


class EditorDetector:
    SUPPORTED_EDITORS: list[str] = ["Code-Insiders", "Code"]
    DEFAULT_EDITOR: str = "Code"

    def __init__(self, path_resolver: PathResolver, fs: FileSystemProtocol):
        self.path_resolver = path_resolver
        self.fs = fs

    def detect_installed_editor(self) -> str:
        for editor in self.SUPPORTED_EDITORS:
            config_dir = self.path_resolver.get_vscode_config_dir(editor)
            if config_dir and self.fs.exists(config_dir):
                return editor
        return self.DEFAULT_EDITOR


class AgentInstaller:
    SOURCE_FILES: list[str] = [
        "instructions/journaling.instructions.md",
    ]

    LOCAL_FILES: list[FileMapping] = [FileMapping(src, src) for src in SOURCE_FILES]

    GLOBAL_FILES: list[FileMapping] = [
        FileMapping(src, f"prompts/{Path(src).name}") for src in SOURCE_FILES
    ]

    def __init__(
        self,
        agent_files_dir: Path,
        fs: FileSystemProtocol,
        path_resolver: PathResolver,
        editor_detector: EditorDetector,
        logger: logging.Logger,
    ):
        self.agent_files_dir = agent_files_dir
        self.fs = fs
        self.path_resolver = path_resolver
        self.editor_detector = editor_detector
        self.logger = logger

    def _validate_source_files(self) -> bool:
        if not self.fs.exists(self.agent_files_dir):
            self.logger.error(f"❌ Error: Agent files directory not found: {self.agent_files_dir}")
            return False
        return True

    def install_files(
        self, target_dir: Path, files: list[FileMapping], dry_run: bool = False
    ) -> InstallationResult:
        if not self._validate_source_files():
            return InstallationResult(
                success=False, files_copied=0, target_dir=target_dir,
                error_message="Agent files directory not found",
            )

        self.logger.info(f"📁 Target directory: {target_dir}")

        if dry_run:
            self.logger.info("\n🔍 DRY RUN - Files that would be copied:")
            for file_map in files:
                src = self.agent_files_dir / file_map.src_relative
                dst = target_dir / file_map.dst_relative
                self.logger.info(f"  {src} -> {dst}")
            return InstallationResult(success=True, files_copied=len(files), target_dir=target_dir)

        return self._perform_installation(target_dir, files)

    def _perform_installation(
        self, target_dir: Path, files: list[FileMapping]
    ) -> InstallationResult:
        copied = 0
        failed = 0
        try:
            for file_map in files:
                dst = target_dir / file_map.dst_relative
                self.fs.mkdir(dst.parent, parents=True, exist_ok=True)

            for file_map in files:
                src = self.agent_files_dir / file_map.src_relative
                dst = target_dir / file_map.dst_relative

                if not self.fs.exists(src):
                    self.logger.warning(f"⚠️  Warning: Source file not found: {src}")
                    failed += 1
                    continue

                self.fs.copy_file(src, dst)
                self.logger.info(f"✅ Copied: {file_map.dst_relative}")
                copied += 1

            if copied > 0:
                self.logger.info(f"\n🎉 Successfully installed {copied} file(s) to {target_dir}")
                return InstallationResult(
                    success=True, files_copied=copied, target_dir=target_dir, files_failed=failed,
                )

            self.logger.error("\n❌ No files were copied")
            return InstallationResult(
                success=False, files_copied=0, target_dir=target_dir,
                error_message="No files were copied", files_failed=failed,
            )

        except OSError as e:
            error_msg = f"Error during installation: {e}"
            self.logger.error(f"❌ {error_msg}")
            return InstallationResult(
                success=False, files_copied=copied, target_dir=target_dir,
                error_message=error_msg, files_failed=len(files) - copied,
            )

    def install_local(self, dry_run: bool = False) -> InstallationResult:
        target_dir = self.path_resolver.get_local_install_dir()
        self.logger.info("📦 Installing journaling instructions locally...")
        return self.install_files(target_dir, self.LOCAL_FILES, dry_run)

    def install_global(
        self, editor: str | None = None, dry_run: bool = False
    ) -> InstallationResult:
        if editor is None:
            editor = self.editor_detector.detect_installed_editor()
            self.logger.info(f"🔍 Auto-detected editor: {editor}")

        config_dir = self.path_resolver.get_vscode_config_dir(editor)

        if config_dir is None or not self.fs.exists(config_dir):
            error_msg = f"Could not find {editor} configuration directory"
            self.logger.error(f"❌ Error: {error_msg}")
            self.logger.info("\n💡 Tip: Use --insiders flag for VS Code Insiders")
            return InstallationResult(
                success=False, files_copied=0, target_dir=config_dir or Path(),
                error_message=error_msg,
            )

        self.logger.info(f"🌍 Installing journaling instructions globally for {editor}...")
        return self.install_files(config_dir, self.GLOBAL_FILES, dry_run)


def create_installer(
    agent_files_dir: Path | None = None,
    logger: logging.Logger | None = None,
) -> AgentInstaller:
    if agent_files_dir is None:
        agent_files_dir = Path(__file__).parent / "agent_files"
    if logger is None:
        logger = setup_logging()

    fs = RealFileSystem()
    env = RealEnvironment()
    path_resolver = PathResolver(env, fs)
    editor_detector = EditorDetector(path_resolver, fs)

    return AgentInstaller(
        agent_files_dir=agent_files_dir, fs=fs, path_resolver=path_resolver,
        editor_detector=editor_detector, logger=logger,
    )


def main() -> int:
    from .__version__ import __version__

    parser = argparse.ArgumentParser(
        description="Install Copilot Journal instruction files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Install locally to current repository (default)
  copilot-journal

  # Install globally to VS Code
  copilot-journal --global

  # Install globally to VS Code Insiders
  copilot-journal --global --insiders

  # Dry run to see what would be installed
  copilot-journal --global --dry-run
        """,
    )

    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--global", "-g", dest="install_global", action="store_true",
                        help="Install globally to VS Code config directory")
    parser.add_argument("--local", "-l", dest="install_local", action="store_true",
                        help="Install locally to .github directory (default)")
    parser.add_argument("--insiders", "-i", action="store_true",
                        help="Install for VS Code Insiders")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Show what would be installed without copying")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="Set logging level")
    parser.add_argument("--log-file", type=Path, help="Write logs to file")

    args = parser.parse_args()

    if args.install_global and args.install_local:
        print("❌ Error: Cannot specify both --global and --local")
        return 1

    logger = setup_logging(level=args.log_level, log_file=args.log_file)
    installer = create_installer(logger=logger)
    logger.info(f"🖥️  System: {platform.system()}")
    logger.info("")

    if args.install_global:
        editor = (
            EditorDetector.SUPPORTED_EDITORS[0] if args.insiders
            else EditorDetector.DEFAULT_EDITOR
        )
        result = installer.install_global(editor, args.dry_run)
    else:
        result = installer.install_local(args.dry_run)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
