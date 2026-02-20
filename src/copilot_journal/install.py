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
    """Supported operating systems for path resolution."""

    WINDOWS = "Windows"
    DARWIN = "Darwin"
    LINUX = "Linux"


class FileSystemProtocol(Protocol):
    """Abstraction for file system operations, enabling test doubles.

    Defines the contract for all file I/O used by the installer.
    Production code uses RealFileSystem; tests inject fakes to avoid
    touching the real filesystem.

    Business context:
        Decouples installer logic from OS-level I/O so installation
        can be fully tested without creating real files or directories.
    """

    def exists(self, path: Path) -> bool:
        """Check whether a filesystem path exists.

        Args:
            path: Absolute or relative path to check.

        Returns:
            True if the path exists on disk, False otherwise.

        Raises:
            None: This method should not raise exceptions; non-existent
                paths return False rather than raising.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> fs.exists(Path("/home/user/project/.git"))
            True
            >>> fs.exists(Path("/nonexistent"))
            False

        Business context:
            Used by PathResolver and EditorDetector to probe for .git
            directories and VS Code config folders before installation.

        See Also:
            mkdir: Creates directories whose existence this method checks.
            read_text: Reads files that this method confirms exist.
        """
        ...

    def mkdir(
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None:
        """Create a directory, optionally with parent directories.

        Args:
            path: Directory path to create.
            parents: If True, create missing parent directories.
            exist_ok: If True, don't raise if directory already exists.

        Returns:
            None

        Raises:
            FileExistsError: If path exists and exist_ok is False.
            OSError: If directory creation fails.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> fs.mkdir(Path("/tmp/a/b/c"), parents=True, exist_ok=True)
            >>> fs.exists(Path("/tmp/a/b/c"))
            True

        Business context:
            Called by _perform_installation() to ensure destination
            directories (instructions/, prompts/) exist before copying
            agent files into them.

        See Also:
            exists: Checks whether the created directory already exists.
            copy_file: Copies files into directories created by mkdir.
        """
        ...

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy a file from src to dst, preserving metadata.

        Args:
            src: Source file path. Must exist.
            dst: Destination file path. Parent directory must exist.

        Returns:
            None

        Raises:
            FileNotFoundError: If src does not exist.
            OSError: If copy operation fails.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> fs.copy_file(Path("agent_files/instructions/j.md"), Path(".github/instructions/j.md"))

        Business context:
            Core operation in _perform_installation() that deploys each
            agent instruction and prompt file to the install target.

        See Also:
            mkdir: Creates destination directories before copy_file runs.
            exists: Validates source file existence before copying.
        """
        ...

    def read_text(self, path: Path) -> str:
        """Read a file and return its contents as a UTF-8 string.

        Args:
            path: Path to the file to read.

        Returns:
            File contents decoded as UTF-8.

        Raises:
            FileNotFoundError: If path does not exist.
            OSError: If file cannot be read.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> content = fs.read_text(Path(".github/instructions/journaling.instructions.md"))
            >>> "{{JOURNAL_PATH}}" in content
            True

        Business context:
            Used by _apply_template_vars() to read installed files so
            ``{{JOURNAL_PATH}}`` placeholders can be detected and replaced.

        See Also:
            write_text: Writes back content after template substitution.
        """
        ...

    def write_text(self, path: Path, content: str) -> None:
        """Write a UTF-8 string to a file, replacing existing content.

        Args:
            path: Path to the file to write.
            content: String content to write.

        Returns:
            None

        Raises:
            OSError: If file cannot be written.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> fs.write_text(Path(".github/instructions/j.md"), "updated content")

        Business context:
            Used by _apply_template_vars() to persist files after
            ``{{JOURNAL_PATH}}`` template substitution.

        See Also:
            read_text: Reads file content before write_text overwrites it.
        """
        ...

    def get_cwd(self) -> Path:
        """Return the current working directory.

        Args:
            None

        Returns:
            Absolute Path to the current working directory.

        Raises:
            OSError: If the current directory has been deleted or is
                otherwise inaccessible.

        Examples:
            >>> fs: FileSystemProtocol = get_fs()
            >>> cwd = fs.get_cwd()
            >>> cwd.is_absolute()
            True

        Business context:
            Used by PathResolver to locate the nearest .git directory
            when determining the local install target.

        See Also:
            exists: Used alongside get_cwd to probe for .git directories.
        """
        ...


class EnvironmentProtocol(Protocol):
    """Abstraction for environment queries (OS, env vars, home dir).

    Defines the contract for platform detection and environment access.
    Production code uses RealEnvironment; tests inject fakes to simulate
    different operating systems and configurations.

    Business context:
        Enables cross-platform testing by decoupling OS detection from
        the actual runtime environment.
    """

    def get_system(self) -> str:
        """Return the operating system platform name.

        Args:
            None

        Returns:
            One of 'Linux', 'Darwin', or 'Windows' matching
            platform.system() output.

        Raises:
            None: Always returns a string; unrecognised platforms are
                handled by the caller (PathResolver.__init__).

        Examples:
            >>> env: EnvironmentProtocol = get_env()
            >>> env.get_system() in ('Linux', 'Darwin', 'Windows')
            True

        Business context:
            Drives OS-specific path resolution in PathResolver.
            The returned value selects the OperatingSystem enum member
            that determines all config directory paths.

        See Also:
            get_home: Provides the base directory that get_system's
                result helps qualify.
            get_env_var: Retrieves OS-specific env vars guided by
                the platform get_system identifies.
        """
        ...

    def get_env_var(self, name: str, default: str = "") -> str:
        """Retrieve an environment variable value.

        Args:
            name: Environment variable name (e.g. 'APPDATA').
            default: Value returned if the variable is not set.

        Returns:
            The variable's value, or default if unset.

        Raises:
            None: Returns the default value rather than raising when
                the variable is not set.

        Examples:
            >>> env: EnvironmentProtocol = get_env()
            >>> env.get_env_var('APPDATA', 'C:\\Users\\user\\AppData\\Roaming')
            'C:\\Users\\user\\AppData\\Roaming'
            >>> env.get_env_var('NONEXISTENT', 'fallback')
            'fallback'

        Business context:
            Used on Windows to locate APPDATA for VS Code config paths.
            Without APPDATA, global installation on Windows cannot resolve
            the target directory.

        See Also:
            get_system: Determines which env vars are relevant per OS.
            get_home: Alternative base path on non-Windows platforms.
        """
        ...

    def get_home(self) -> Path:
        """Return the user's home directory.

        Args:
            None

        Returns:
            Absolute Path to the home directory (e.g. /home/user).

        Raises:
            RuntimeError: If the home directory cannot be determined
                (e.g. HOME env var unset and no passwd entry).

        Examples:
            >>> env: EnvironmentProtocol = get_env()
            >>> home = env.get_home()
            >>> home.is_absolute()
            True

        Business context:
            Base path for VS Code config on Linux (~/.config) and
            macOS (~/Library/Application Support). On Windows,
            get_env_var('APPDATA') is used instead.

        See Also:
            get_env_var: Windows alternative for locating config base.
            get_system: Determines whether get_home or get_env_var
                provides the config base path.
        """
        ...


class RealFileSystem:
    """Production file system using pathlib and shutil.

    Implements FileSystemProtocol for real OS file operations.
    All methods are thin delegates excluded from coverage since
    they wrap standard library calls with no branching logic.

    Business context:
        Injected into AgentInstaller at runtime. Swapped for fakes
        in tests to avoid filesystem side effects.
    """

    def exists(self, path: Path) -> bool:  # pragma: no cover
        """Check whether a filesystem path exists.

        Delegates to ``Path.exists()``.

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.

        Raises:
            None: Thin delegate; no additional exceptions raised.

        Examples:
            >>> fs = RealFileSystem()
            >>> fs.exists(Path('/tmp'))
            True

        Business context:
            Called during installation to verify destination directories
            and to detect whether agent files already exist before
            deciding whether to overwrite them.

        See Also:
            FileSystemProtocol.exists: Protocol definition this implements.
        """
        return path.exists()

    def mkdir(  # pragma: no cover
        self, path: Path, parents: bool = False, exist_ok: bool = False
    ) -> None:
        """Create a directory, optionally with parents, via ``Path.mkdir()``.

        Thin delegate to the standard library. Excluded from coverage.

        Args:
            path: Directory path to create.
            parents: Create parent directories if missing.
            exist_ok: Suppress error if directory exists.

        Returns:
            None

        Raises:
            FileExistsError: If path exists and exist_ok is False.

        Examples:
            >>> fs = RealFileSystem()
            >>> fs.mkdir(Path('/tmp/journal/prompts'), parents=True, exist_ok=True)

        Business context:
            Used by _perform_installation() to ensure destination
            directories exist before copying agent files.

        See Also:
            FileSystemProtocol.mkdir: Protocol definition this implements.
        """
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def copy_file(self, src: Path, dst: Path) -> None:  # pragma: no cover
        """Copy a single file with metadata preservation via ``shutil.copy2()``.

        Thin delegate to the standard library. Excluded from coverage.

        Args:
            src: Source file path.
            dst: Destination file path.

        Returns:
            None

        Raises:
            FileNotFoundError: If src does not exist.

        Examples:
            >>> fs = RealFileSystem()
            >>> fs.copy_file(Path('agent_files/journaling.md'), Path('.github/instructions/journaling.md'))

        Business context:
            Core operation in _perform_installation() for deploying
            agent instruction and prompt files.

        See Also:
            FileSystemProtocol.copy_file: Protocol definition this implements.
        """
        shutil.copy2(src, dst)

    def read_text(self, path: Path) -> str:  # pragma: no cover
        """Read file contents as a UTF-8 string.

        Args:
            path: Path to the file.

        Returns:
            File contents decoded as UTF-8.

        Raises:
            FileNotFoundError: If path does not exist.

        Examples:
            >>> fs = RealFileSystem()
            >>> content = fs.read_text(Path('.github/instructions/journaling.instructions.md'))

        Business context:
            Used during installation to read agent file contents for
            comparison when deciding whether existing files need updating.

        See Also:
            FileSystemProtocol.read_text: Protocol definition this implements.
        """
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:  # pragma: no cover
        """Write a UTF-8 string to a file, replacing existing content.

        Args:
            path: Path to the file.
            content: String to write.

        Returns:
            None

        Raises:
            OSError: If write fails.

        Examples:
            >>> fs = RealFileSystem()
            >>> fs.write_text(Path('output.md'), '# Daily Summary\n')

        Business context:
            Used to write generated or modified agent configuration
            files to the workspace during installation.

        See Also:
            FileSystemProtocol.write_text: Protocol definition this implements.
        """
        path.write_text(content, encoding="utf-8")

    def get_cwd(self) -> Path:  # pragma: no cover
        """Return the current working directory as an absolute path.

        Thin delegate to ``Path.cwd()``. Excluded from coverage.

        Args:
            None: Parameterless method.

        Returns:
            Absolute Path to the current working directory.

        Raises:
            None: Thin delegate; no additional exceptions raised.

        Business context:
            Used by PathResolver.get_local_install_dir() as the starting
            point for walking up to find the nearest .git directory.

        Examples:
            >>> fs = RealFileSystem()
            >>> fs.get_cwd()
            PosixPath('/home/user/project')

        See Also:
            FileSystemProtocol.get_cwd: Protocol definition this implements.
        """
        return Path.cwd()


class RealEnvironment:
    """Production environment using platform and os modules.

    Implements EnvironmentProtocol for real runtime detection.
    Excluded from coverage as thin standard-library delegates.

    Business context:
        Injected into PathResolver at runtime. Tests inject fakes
        to simulate Windows/macOS/Linux without changing the actual OS.
    """

    def get_system(self) -> str:  # pragma: no cover
        """Return the OS platform name as a string.

        Thin delegate to ``platform.system()``. Excluded from coverage.

        Args:
            None: Parameterless method.

        Returns:
            One of 'Linux', 'Darwin', or 'Windows' — used by
            PathResolver to select OS-specific config paths.

        Raises:
            None: Thin delegate; no additional exceptions raised.

        Business context:
            Drives the OperatingSystem enum selection in PathResolver,
            which determines all subsequent path resolution logic.

        Examples:
            >>> env = RealEnvironment()
            >>> env.get_system()
            'Linux'

        See Also:
            EnvironmentProtocol.get_system: Protocol definition this implements.
        """
        return platform.system()

    def get_env_var(self, name: str, default: str = "") -> str:  # pragma: no cover
        """Retrieve an environment variable with an optional fallback.

        Thin delegate to ``os.environ.get()``. Excluded from coverage.

        Args:
            name: Variable name (e.g. 'APPDATA' on Windows).
            default: Fallback value if the variable is unset.

        Returns:
            Variable value or default.

        Raises:
            None: Thin delegate; no additional exceptions raised.

        Business context:
            Used by PathResolver on Windows to locate the APPDATA
            directory for VS Code configuration paths.

        Examples:
            >>> env = RealEnvironment()
            >>> env.get_env_var('HOME', '/fallback')
            '/home/user'

        See Also:
            EnvironmentProtocol.get_env_var: Protocol definition this implements.
        """
        return os.environ.get(name, default)

    def get_home(self) -> Path:  # pragma: no cover
        """Return the user home directory as an absolute path.

        Thin delegate to ``Path.home()``. Excluded from coverage.

        Args:
            None: Parameterless method.

        Returns:
            Absolute Path to the home directory.

        Raises:
            None: Thin delegate; no additional exceptions raised.

        Business context:
            Base path for VS Code config resolution on Linux (~/.config)
            and macOS (~/Library/Application Support).

        Examples:
            >>> env = RealEnvironment()
            >>> env.get_home()
            PosixPath('/home/user')

        See Also:
            EnvironmentProtocol.get_home: Protocol definition this implements.
        """
        return Path.home()


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    logger_name: str = "copilot_journal",
) -> logging.Logger:
    """Configure and return a logger with console and optional file output.

    Creates a named logger with a stdout console handler. Optionally adds
    a file handler with timestamped format. Clears any existing handlers
    to prevent duplicate output on repeated calls.

    Business context:
        Provides consistent CLI output formatting for the installer.
        File logging enables debugging install issues in CI/CD pipelines.

    Args:
        level: Log level string. Must be one of DEBUG, INFO, WARNING,
            ERROR, or CRITICAL (case-insensitive).
        log_file: Optional path for file logging. Parent directories
            are created automatically if they don't exist.
        logger_name: Name passed to ``logging.getLogger()``.

    Returns:
        Configured ``logging.Logger`` with propagation disabled.

    Raises:
        ValueError: If level is not a recognized log level string.

    Examples:
        >>> logger = setup_logging("DEBUG")
        >>> logger.name
        'copilot_journal'
        >>> setup_logging("INFO", log_file=Path("/tmp/install.log"))
    """
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
    """Maps a source file path to its destination path during installation."""

    src_relative: str
    dst_relative: str


@dataclass(frozen=True, slots=True)
class InstallationResult:
    """Outcome of an install operation: success/failure, counts, and errors."""

    success: bool
    files_copied: int
    target_dir: Path
    error_message: str | None = None
    files_failed: int = 0


class PathResolver:
    """Resolve VS Code configuration and local install directories per OS.

    Maps editor variants ('Code', 'Code-Insiders') to their platform-specific
    User config directories. Also locates the nearest git repository root
    to determine the local ``.github`` install target.

    Business context:
        Central path logic for the installer. Supports Windows (APPDATA),
        macOS (Library/Application Support), and Linux (~/.config) layouts.
        Testable via injected EnvironmentProtocol and FileSystemProtocol.

    Examples:
        >>> resolver = PathResolver(env, fs)
        >>> resolver.get_vscode_config_dir("Code")
        PosixPath('/home/user/.config/Code/User')
    """

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

    def __init__(self, env: EnvironmentProtocol, fs: FileSystemProtocol) -> None:
        """Initialize path resolver with environment and filesystem abstractions.

        Detects the current operating system and stores it for subsequent
        path resolution calls.

        Args:
            env: Environment abstraction for OS detection and env vars.
            fs: Filesystem abstraction for existence checks.

        Returns:
            None

        Raises:
            ValueError: If the detected OS is not in OperatingSystem enum
                (i.e., not Windows, Darwin, or Linux).

        Business context:
            PathResolver is the first object created during both local and
            global install flows — it normalises OS differences so that
            downstream helpers (get_vscode_config_dir, get_local_install_dir)
            work identically across platforms.

        Examples:
            >>> resolver = PathResolver(RealEnvironment(), RealFileSystem())
            >>> resolver.system
            <OperatingSystem.LINUX: 'Linux'>

        See Also:
            EditorDetector: Uses PathResolver to locate editor config dirs.
            AgentInstaller: Consumes resolved paths for file installation.
        """
        self.env = env
        self.fs = fs
        system_str = env.get_system()
        try:
            self.system = OperatingSystem(system_str)
        except ValueError:
            raise ValueError(f"Unsupported operating system: {system_str}") from None

    def get_vscode_config_dir(self, editor: str) -> Path | None:
        """Return the VS Code User config directory for an editor variant.

        Constructs the platform-specific path to the VS Code User directory
        where global prompts and instructions are stored.

        On Windows, uses the APPDATA environment variable as the base path.
        On Linux/macOS, uses the user's home directory.

        Args:
            editor: Editor variant name — either 'Code' or 'Code-Insiders'.

        Returns:
            Absolute Path to the User config directory, or None if the editor
            is not recognized or APPDATA is unset on Windows.

        Business context:
            Used by install_global() to determine where to copy agent files
            for system-wide Copilot access across all projects.

        Examples:
            >>> resolver.get_vscode_config_dir("Code")
            PosixPath('/home/user/.config/Code/User')
            >>> resolver.get_vscode_config_dir("Unknown")
        """
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
        """Locate the nearest git repo root and return its .github directory.

        Walks up from the current working directory looking for a ``.git``
        directory. Returns ``<repo_root>/.github`` if found, otherwise
        falls back to ``<cwd>/.github``.

        Args:
            None — uses the filesystem abstraction's current working directory.

        Returns:
            Path to the ``.github`` directory adjacent to the nearest ``.git``.

        Raises:
            None — always returns a valid Path (falls back to cwd/.github).

        Business context:
            Ensures agent files are installed at the repository level so
            they're committed alongside the project and shared with all
            contributors.

        Examples:
            >>> # If cwd is /home/user/project/src and .git is at /home/user/project
            >>> resolver.get_local_install_dir()
            PosixPath('/home/user/project/.github')

        See Also:
            get_vscode_config_dir: Resolves the global editor config path.
            AgentInstaller.install_local: Calls this to find the target dir.
        """
        current = self.fs.get_cwd()
        while current.parent != current:
            if self.fs.exists(current / ".git"):
                return current / ".github"
            current = current.parent
        return self.fs.get_cwd() / ".github"


class EditorDetector:
    """Detect which VS Code variant is installed on the system.

    Checks for Code-Insiders first (preferred), then stable Code.
    Falls back to DEFAULT_EDITOR if neither config directory is found.

    Business context:
        Enables zero-config global installation — users don't need to
        specify which editor variant they have installed.

    Examples:
        >>> detector = EditorDetector(resolver, fs)
        >>> detector.detect_installed_editor()
        'Code-Insiders'
    """

    SUPPORTED_EDITORS: list[str] = ["Code-Insiders", "Code"]
    DEFAULT_EDITOR: str = "Code"

    def __init__(self, path_resolver: PathResolver, fs: FileSystemProtocol) -> None:
        """Initialize editor detector with path resolver and filesystem.

        Stores dependencies for probing VS Code config directories
        to determine which editor variant is installed.

        Args:
            path_resolver: Resolver for VS Code config directory paths.
            fs: Filesystem abstraction for checking directory existence.

        Returns:
            None

        Raises:
            None — constructor only stores references; no validation performed.

        Business context:
            Dependencies are injected to support testing with fake
            filesystems that simulate different editor installations.

        Examples:
            >>> detector = EditorDetector(resolver, fake_fs)
            >>> detector.detect_installed_editor()
            'Code'

        See Also:
            PathResolver: Provides the config directory paths probed here.
            AgentInstaller: Calls detect_installed_editor during global install.
        """
        self.path_resolver = path_resolver
        self.fs = fs

    def detect_installed_editor(self) -> str:
        """Probe for installed VS Code variants and return the first match.

        Checks SUPPORTED_EDITORS in order (Insiders first, then stable).
        Each check resolves the config directory path and tests existence.

        Args:
            None — reads SUPPORTED_EDITORS class attribute and probes
            the filesystem via the injected path_resolver and fs.

        Returns:
            Editor name string ('Code-Insiders' or 'Code'). Returns
            DEFAULT_EDITOR ('Code') if no config directory is found.

        Raises:
            None — always returns a valid editor name string.

        Business context:
            Called by install_global() when the user doesn't specify
            an editor via --insiders flag.

        Examples:
            >>> detector.detect_installed_editor()
            'Code'

        See Also:
            PathResolver.get_vscode_config_dir: Resolves each editor's path.
            SUPPORTED_EDITORS: Ordered list defining probe priority.
        """
        for editor in self.SUPPORTED_EDITORS:
            config_dir = self.path_resolver.get_vscode_config_dir(editor)
            if config_dir and self.fs.exists(config_dir):
                return editor
        return self.DEFAULT_EDITOR


class AgentInstaller:
    """Copy agent instruction and prompt files to local or global targets.

    Manages the full installation workflow: validate source files exist,
    create destination directories, copy files, and substitute template
    variables (e.g. ``{{JOURNAL_PATH}}``) in the installed copies.

    Business context:
        Core installer class that enables both per-repo (local) and
        system-wide (global) deployment of Copilot journaling files.
        Local installs go to ``.github/``; global installs go to the
        VS Code User config directory.

    Examples:
        >>> installer = create_installer(journal_path="docs/journal")
        >>> result = installer.install_local()
        >>> result.success
        True
    """

    SOURCE_FILES: list[str] = [
        "instructions/journaling.instructions.md",
        "prompts/daily-summary.prompt.md",
        "prompts/setup-dendron-vault.prompt.md",
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
        journal_path: str = "docs/vault",
    ):
        """Initialize the installer with all dependencies.

        Args:
            agent_files_dir: Directory containing bundled agent files
                (instructions/ and prompts/ subdirectories).
            fs: Filesystem abstraction for all I/O operations.
            path_resolver: Resolves target directories per OS.
            editor_detector: Detects installed VS Code variant.
            logger: Logger for installation progress messages.
            journal_path: Value substituted for ``{{JOURNAL_PATH}}``
                in installed template files. Defaults to 'docs/vault'.

        Returns:
            None

        Raises:
            None

        Examples:
            >>> installer = AgentInstaller(
            ...     agent_files_dir=Path("agent_files"),
            ...     fs=RealFileSystem(),
            ...     path_resolver=resolver,
            ...     editor_detector=detector,
            ...     logger=logging.getLogger(__name__),
            ...     journal_path="docs/vault",
            ... )

        Business context:
            Use ``create_installer()`` factory for production. Direct
            construction is mainly for testing with injected fakes.

        See Also:
            ``create_installer``: Factory that wires production dependencies.
        """
        self.agent_files_dir = agent_files_dir
        self.fs = fs
        self.path_resolver = path_resolver
        self.editor_detector = editor_detector
        self.logger = logger
        self.journal_path = journal_path

    def _validate_source_files(self) -> bool:
        """Verify that the agent_files_dir exists on the filesystem.

        Logs an error message if the directory is missing.

        Args:
            None (uses instance attribute ``self.agent_files_dir``).

        Returns:
            True if agent_files_dir exists, False otherwise.

        Raises:
            None

        Examples:
            >>> installer._validate_source_files()
            True

        Business context:
            Guard check before any file copy operations. Catches
            broken installations where the package data is missing.

        See Also:
            ``install_files``: Calls this as its first validation step.
        """
        if not self.fs.exists(self.agent_files_dir):
            self.logger.error(f"❌ Error: Agent files directory not found: {self.agent_files_dir}")
            return False
        return True

    def _apply_template_vars(self, target_dir: Path, files: list[FileMapping]) -> None:
        """Replace ``{{JOURNAL_PATH}}`` in installed files with the configured path.

        Reads each destination file, performs string replacement, and writes
        back. Silently skips files that can't be read (non-critical).

        Args:
            target_dir: Base directory where files were installed.
            files: File mappings whose destinations may contain template vars.

        Returns:
            None

        Raises:
            None — ``OSError`` from file I/O is caught and silently ignored
            since template substitution is non-critical.

        Examples:
            >>> installer._apply_template_vars(
            ...     Path(".github"), AgentInstaller.LOCAL_FILES
            ... )

        Business context:
            Allows the same source templates to be customized per-project
            with different journal storage locations.

        See Also:
            ``_perform_installation``: Calls this after copying files.
        """
        for file_map in files:
            dst = target_dir / file_map.dst_relative
            try:
                content = self.fs.read_text(dst)
                if "{{JOURNAL_PATH}}" in content:
                    content = content.replace("{{JOURNAL_PATH}}", self.journal_path)
                    self.fs.write_text(dst, content)
                    self.logger.debug(f"📝 Applied journal path to: {file_map.dst_relative}")
            except OSError:
                pass  # Non-critical — file was still copied

    def install_files(
        self, target_dir: Path, files: list[FileMapping], dry_run: bool = False
    ) -> InstallationResult:
        """Copy agent files to target_dir, substituting template variables.

        Validates that source files exist, creates destination directories,
        copies each file, and applies template variable substitution.
        In dry-run mode, logs what would be copied without writing.

        Args:
            target_dir: Destination directory for installed files.
            files: File mappings (source -> destination relative paths).
            dry_run: If True, only log planned actions without copying.

        Returns:
            InstallationResult with success status, file counts, and any
            error messages.

        Business context:
            Shared implementation for both install_local() and
            install_global(). Dry-run mode lets users preview changes
            before committing to them.

        Examples:
            >>> result = installer.install_files(Path(".github"), installer.LOCAL_FILES)
            >>> result.files_copied
            3
        """
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
        """Execute the file copy loop and apply template variable substitution.

        Creates all destination directories first, then copies files one by
        one. Missing source files are logged as warnings and counted as
        failures. After successful copies, applies template variable
        substitution via ``_apply_template_vars()``.

        Args:
            target_dir: Base destination directory.
            files: File mappings to copy.

        Returns:
            InstallationResult with success=True if at least one file
            was copied, False if none were copied or an OSError occurred.

        Raises:
            OSError: Caught internally during directory creation or file
                copy operations. Returned as an error in the result rather
                than propagated to the caller.

        Examples:
            >>> result = installer._perform_installation(
            ...     Path(".github"), AgentInstaller.LOCAL_FILES
            ... )
            >>> result.success
            True

        Business context:
            Separated from install_files() to isolate the actual I/O
            from validation and dry-run logic.

        See Also:
            ``install_files``: Public method that delegates here after validation.
            ``_apply_template_vars``: Called after successful file copies.
        """
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
                self._apply_template_vars(target_dir, files)
                self.logger.info(f"\n🎉 Successfully installed {copied} file(s) to {target_dir}")
                self.logger.info(f"📓 Journal path set to: {self.journal_path}")
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
        """Install agent files to the nearest repo's ``.github`` directory for local project use.

        Locates the git repository root by walking up from cwd, then
        copies instruction and prompt files into ``.github/``.

        Args:
            dry_run: If True, only log planned actions without copying.

        Returns:
            InstallationResult with success status and file counts.

        Raises:
            RuntimeError: If ``PathResolver.get_local_install_dir()`` cannot
                locate a git repository root from the current directory.

        Business context:
            Default install mode. Files in ``.github/`` are committed
            with the project, enabling team-wide journaling.

        Examples:
            >>> result = installer.install_local()
            >>> result.target_dir
            PosixPath('/home/user/project/.github')

        See Also:
            ``install_global``: Alternative mode for user-wide installation.
            ``install_files``: Shared implementation used by both modes.
        """
        target_dir = self.path_resolver.get_local_install_dir()
        self.logger.info("📦 Installing journaling instructions locally...")
        return self.install_files(target_dir, self.LOCAL_FILES, dry_run)

    def install_global(
        self, editor: str | None = None, dry_run: bool = False
    ) -> InstallationResult:
        """Install agent files to the VS Code global User config directory.

        Auto-detects the editor variant if not specified. Resolves the
        platform-specific config path and copies files there. Falls back
        with a helpful tip if the config directory cannot be found.

        Args:
            editor: VS Code variant — 'Code' or 'Code-Insiders'.
                Auto-detected via EditorDetector if None.
            dry_run: If True, only log planned actions without copying.

        Returns:
            InstallationResult with success status and file counts.

        Business context:
            Global install makes journaling available across all projects
            without per-repo setup. Useful for individual developers who
            want journaling everywhere.

        Examples:
            >>> result = installer.install_global("Code-Insiders")
            >>> result.success
            True
        """
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
    journal_path: str = "docs/vault",
) -> AgentInstaller:
    """Build an AgentInstaller wired with real filesystem and environment.

    Factory function that creates production-ready dependencies
    (RealFileSystem, RealEnvironment, PathResolver, EditorDetector)
    and assembles them into a configured AgentInstaller.

    Args:
        agent_files_dir: Directory containing bundled agent source files.
            Defaults to the ``agent_files/`` subdirectory adjacent to
            this module.
        logger: Logger for installation messages. If None, creates one
            via ``setup_logging()`` with default settings.
        journal_path: Value substituted for ``{{JOURNAL_PATH}}`` template
            variables in installed files.

    Returns:
        Configured AgentInstaller ready for ``install_local()`` or
        ``install_global()`` calls.

    Raises:
        None

    Business context:
        Primary entry point for programmatic usage. Encapsulates all
        dependency wiring so callers don't need to know about
        PathResolver, EditorDetector, or filesystem abstractions.

    Examples:
        >>> installer = create_installer(journal_path="docs/journal")
        >>> result = installer.install_local()

    See Also:
        ``AgentInstaller``: The class this factory constructs.
        ``main``: CLI entry point that calls this factory.
    """
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
        editor_detector=editor_detector, logger=logger, journal_path=journal_path,
    )


def main() -> int:
    """CLI entry point for copilot-journal.

    Parses command-line arguments and runs either a local or global
    installation of Copilot Journal agent files. Supports interactive
    journal path prompting when stdin is a TTY.

    The precedence for journal path is:
    CLI ``--journal-path`` arg > interactive prompt > default 'docs/vault'.

    Args:
        None (uses ``argparse`` to parse ``sys.argv``).

    Returns:
        Exit code: 0 on successful installation, 1 on failure or
        invalid argument combinations.

    Raises:
        SystemExit: Raised by ``argparse`` for ``--help``, ``--version``,
            or unrecognized arguments.

    Business context:
        Registered as the ``copilot-journal`` console_scripts entry point
        in pyproject.toml. Provides the primary user-facing CLI.

    Examples:
        >>> # Equivalent to: copilot-journal --local --journal-path docs/journal
        >>> sys.argv = ['copilot-journal', '--local', '-j', 'docs/journal']
        >>> main()
        0

    See Also:
        ``create_installer``: Factory called internally to build the installer.
    """
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
    parser.add_argument("--journal-path", "-j", type=str, default=None,
                        help="Path where journal entries will be stored (default: docs/vault)")
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

    # Determine journal path: CLI arg > interactive prompt > default
    if args.journal_path is not None:
        journal_path = args.journal_path
    elif sys.stdin.isatty() and not args.dry_run:
        default_path = "docs/vault"
        user_input = input(f"📓 Where should journal entries be stored? [{default_path}]: ").strip()
        journal_path = user_input if user_input else default_path
    else:
        journal_path = "docs/vault"

    installer = create_installer(logger=logger, journal_path=journal_path)
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
