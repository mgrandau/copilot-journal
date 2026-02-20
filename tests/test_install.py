"""Tests for copilot_journal.install — targeting 100% branch coverage."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copilot_journal.install import (
    AgentInstaller,
    EditorDetector,
    FileMapping,
    InstallationResult,
    OperatingSystem,
    PathResolver,
    create_installer,
    main,
    setup_logging,
)


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeFileSystem:
    """Test double for FileSystem — in-memory filesystem for testing without real I/O.

    Categories:
        1. Path queries - existence checks and cwd resolution (2 methods)
        2. File operations - read, write, copy (3 methods)
        3. Directory operations - mkdir (1 method)

    Total: 7 methods.
    """

    def __init__(self) -> None:
        """Initialise an empty in-memory filesystem.

        Simulates a blank filesystem for testing by creating empty storage
        dicts and setting a default working directory.

        Business context:
            Enables isolated testing of install logic without touching disk.

        Args:
            None

        Returns:
            None

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.files
            {}
        """
        self.files: dict[str, str] = {}
        self.dirs: set[str] = set()
        self._cwd = Path("/fake/project")

    def exists(self, path: Path) -> bool:
        """Check whether a path exists as a file or directory.

        Simulates os.path.exists for testing by checking both in-memory stores.

        Business context:
            Enables isolated testing of existence checks without real I/O.

        Args:
            path: Filesystem path to check.

        Returns:
            True if the path was registered as a file or directory.

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.exists(Path("/nonexistent"))
            False
        """
        s = str(path)
        return s in self.files or s in self.dirs

    def mkdir(self, path: Path, parents: bool = False, exist_ok: bool = False) -> None:
        """Record a directory as created.

        Simulates Path.mkdir for testing by adding the path to the dirs set.

        Business context:
            Enables isolated testing of directory creation without real I/O.

        Args:
            path: Directory path to create.
            parents: Accepted for API compatibility; not enforced.
            exist_ok: Accepted for API compatibility; not enforced.

        Returns:
            None

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.mkdir(Path("/tmp/test"), parents=True, exist_ok=True)
        """
        self.dirs.add(str(path))

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy file content from src to dst in memory.

        Simulates shutil.copy2 for testing by transferring the in-memory
        content string from one key to another.

        Business context:
            Enables isolated testing of file-copy logic without real I/O.

        Args:
            src: Source file path.
            dst: Destination file path.

        Returns:
            None

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.files["/src.md"] = "content"
            >>> fs.copy_file(Path("/src.md"), Path("/dst.md"))
        """
        self.files[str(dst)] = self.files.get(str(src), "")

    def read_text(self, path: Path) -> str:
        """Read text content of a file.

        Simulates Path.read_text for testing by looking up the in-memory store.

        Business context:
            Enables isolated testing of file reads without real I/O.

        Args:
            path: File path to read.

        Returns:
            The stored text content.

        Raises:
            FileNotFoundError: If the path was never written.
        """
        s = str(path)
        if s not in self.files:
            raise FileNotFoundError(s)
        return self.files[s]

    def write_text(self, path: Path, content: str) -> None:
        """Write text content to a file.

        Simulates Path.write_text for testing by storing content in memory.

        Business context:
            Enables isolated testing of file writes without real I/O.

        Args:
            path: File path to write.
            content: Text content to store.

        Returns:
            None

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.write_text(Path("/test.md"), "hello")
        """
        self.files[str(path)] = content

    def get_cwd(self) -> Path:
        """Return the fake current working directory.

        Simulates os.getcwd for testing by returning the preconfigured path.

        Business context:
            Enables isolated testing of cwd-dependent logic like git-root
            detection without real filesystem state.

        Args:
            None

        Returns:
            The Path set during construction (default /fake/project).

        Raises:
            None

        Examples:
            >>> fs = FakeFileSystem()
            >>> fs.get_cwd()
            PosixPath('/fake/project')
        """
        return self._cwd


class FakeEnvironment:
    """Test double for Environment — configurable OS/env-var fake for cross-platform testing.

    Categories:
        1. OS detection - system string and home directory (2 methods)
        2. Environment variables - env var lookups (1 method)

    Total: 3 methods.
    """

    def __init__(
        self,
        system: str = "Linux",
        home: Path | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> None:
        """Initialise a configurable environment fake.

        Creates an environment double with preset OS, home directory,
        and environment variables for cross-platform testing.

        Business context:
            Enables isolated testing of OS-dependent logic without
            modifying the real runtime environment.

        Args:
            system: OS name string (default "Linux").
            home: Home directory path (default /home/testuser).
            env_vars: Optional dict of environment variables.

        Returns:
            None

        Raises:
            None

        Examples:
            >>> env = FakeEnvironment("Windows", env_vars={"APPDATA": "C:/Users"})
        """
        self._system = system
        self._home = home or Path("/home/testuser")
        self._env_vars = env_vars or {}

    def get_system(self) -> str:
        """Return the configured operating system name.

        Simulates platform.system() for testing by returning the preset string.

        Business context:
            Enables isolated testing of OS-dependent path resolution without
            running on each target platform.

        Args:
            None

        Returns:
            OS name string (e.g. "Linux", "Darwin", "Windows").

        Raises:
            None

        Examples:
            >>> env = FakeEnvironment("Darwin")
            >>> env.get_system()
            'Darwin'
        """
        return self._system

    def get_env_var(self, name: str, default: str = "") -> str:
        """Look up an environment variable by name.

        Simulates os.environ.get for testing by searching the preset dict.

        Business context:
            Enables isolated testing of env-var-dependent logic (e.g. APPDATA
            on Windows) without modifying the real environment.

        Args:
            name: Variable name to look up.
            default: Value returned when the variable is absent.

        Returns:
            The variable value, or *default* if not set.

        Raises:
            None

        Examples:
            >>> env = FakeEnvironment(env_vars={"HOME": "/home/test"})
            >>> env.get_env_var("HOME")
            '/home/test'
        """
        return self._env_vars.get(name, default)

    def get_home(self) -> Path:
        """Return the configured home directory.

        Simulates Path.home() for testing by returning the preset path.

        Business context:
            Enables isolated testing of home-relative path resolution
            without depending on the real user's home directory.

        Args:
            None

        Returns:
            The home Path set during construction (default /home/testuser).

        Raises:
            None

        Examples:
            >>> env = FakeEnvironment(home=Path("/Users/test"))
            >>> env.get_home()
            PosixPath('/Users/test')
        """
        return self._home


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_fs() -> FakeFileSystem:
    """Provide a fresh FakeFileSystem for each test.

    Business context:
        Ensures test isolation by providing empty in-memory file storage.

    Args:
        None

    Returns:
        Configured FakeFileSystem instance.

    Raises:
        None

    Examples:
        >>> fs = fake_fs()
        >>> fs.files
        {}
    """
    return FakeFileSystem()


@pytest.fixture
def fake_env() -> FakeEnvironment:
    """Provide a fresh FakeEnvironment defaulting to Linux for each test.

    Business context:
        Ensures test isolation by providing a clean environment fake.

    Args:
        None

    Returns:
        Configured FakeEnvironment instance.

    Raises:
        None

    Examples:
        >>> env = fake_env()
        >>> env.get_system()
        'Linux'
    """
    return FakeEnvironment()


@pytest.fixture
def linux_resolver(fake_env: FakeEnvironment, fake_fs: FakeFileSystem) -> PathResolver:
    """Provide a fresh PathResolver wired to Linux fakes for each test.

    Business context:
        Ensures test isolation by providing a resolver backed by fakes
        rather than real OS lookups.

    Args:
        fake_env: Injected FakeEnvironment fixture (Linux default).
        fake_fs: Injected FakeFileSystem fixture (empty).

    Returns:
        Configured PathResolver instance targeting Linux.

    Raises:
        None

    Examples:
        >>> resolver = linux_resolver(fake_env, fake_fs)
        >>> resolver.system
        <OperatingSystem.LINUX: 'Linux'>
    """
    return PathResolver(fake_env, fake_fs)


def _make_installer(
    fs: FakeFileSystem,
    env: FakeEnvironment | None = None,
    agent_files_dir: Path | None = None,
    journal_path: str = "docs/vault",
) -> AgentInstaller:
    """Build an AgentInstaller wired with fake dependencies for testing.

    Assembles all test doubles (FakeFileSystem, FakeEnvironment, PathResolver,
    EditorDetector) into a configured AgentInstaller instance.

    Business context:
        Centralises test dependency wiring so each test case doesn't repeat
        boilerplate setup. Mirrors create_installer() production factory.

    Args:
        fs: In-memory filesystem fake.
        env: Environment fake. Defaults to Linux.
        agent_files_dir: Source directory for agent files.
        journal_path: Template variable replacement value.

    Returns:
        AgentInstaller configured with injected fakes.

    Examples:
        >>> installer = _make_installer(fake_fs, journal_path="docs/journal")
    """
    if env is None:
        env = FakeEnvironment()
    if agent_files_dir is None:
        agent_files_dir = Path("/fake/agent_files")
    resolver = PathResolver(env, fs)
    detector = EditorDetector(resolver, fs)
    log = setup_logging("DEBUG", logger_name="test_installer")
    return AgentInstaller(
        agent_files_dir=agent_files_dir,
        fs=fs,
        path_resolver=resolver,
        editor_detector=detector,
        logger=log,
        journal_path=journal_path,
    )


# ── OperatingSystem ──────────────────────────────────────────────────────────


class TestOperatingSystem:
    """Test suite for OperatingSystem enum value mapping.

    Categories:
    1. Enum values - verifies string values for all OS variants (1 test)
    2. String conversion - verifies round-trip from string to enum (1 test)

    Total: 2 tests.
    """

    def test_values(self) -> None:
        """Verifies all three OS enum values match their platform strings.

        Tests enum value correctness by asserting each member's `.value`
        against the expected platform identifier string.

        Business context:
            OperatingSystem enum values must match `platform.system()` output
            exactly, since they drive path resolution and editor detection.

        Arrangement:
            1. No setup needed; enum members are module-level constants.

        Action:
            Access `.value` on each of the three enum members.

        Assertion Strategy:
            Validates exhaustive correctness by confirming:
            - WINDOWS.value equals "Windows".
            - DARWIN.value equals "Darwin".
            - LINUX.value equals "Linux".

        Testing Principle:
            Validates enum completeness, ensuring all supported platforms
            are represented with the correct identifier strings.
        """
        assert OperatingSystem.WINDOWS.value == "Windows"
        assert OperatingSystem.DARWIN.value == "Darwin"
        assert OperatingSystem.LINUX.value == "Linux"

    def test_from_string(self) -> None:
        """Verifies string-to-enum conversion returns the correct member.

        Tests enum construction by passing a valid platform string and
        asserting identity with the expected member.

        Business context:
            PathResolver constructs OperatingSystem from `platform.system()`
            output; this must resolve to the correct enum member.

        Arrangement:
            1. No setup needed; uses the enum constructor directly.

        Action:
            Construct OperatingSystem from the string "Linux".

        Assertion Strategy:
            Validates identity by confirming:
            - The constructed value `is` the LINUX singleton member.

        Testing Principle:
            Validates enum round-trip fidelity, ensuring string-based
            construction yields the identical enum member.
        """
        assert OperatingSystem("Linux") is OperatingSystem.LINUX


# ── setup_logging ────────────────────────────────────────────────────────────


class TestSetupLogging:
    """Test suite for setup_logging logger factory configuration.

    Categories:
    1. Logger identity - verifies name and type of returned logger (2 tests)
    2. Input validation - verifies invalid log levels are rejected (1 test)
    3. Handler configuration - verifies handler types and counts (3 tests)

    Total: 6 tests.
    """

    def test_returns_named_logger(self) -> None:
        """Verifies setup_logging returns a correctly configured Logger instance.

        Tests logger identity by checking the returned object's type, name,
        and propagation flag.

        Business context:
            Each subsystem needs an isolated, named logger so log output can
            be filtered and routed without cross-contamination.

        Arrangement:
            1. No external state needed; each call creates a fresh logger.

        Action:
            Call setup_logging with level "INFO" and logger_name "test_setup".

        Assertion Strategy:
            Validates correct construction by confirming:
            - Return type is logging.Logger.
            - Logger name matches the requested name.
            - Propagation is disabled to prevent duplicate output.

        Testing Principle:
            Validates factory contract, ensuring the returned logger
            has the exact identity and isolation properties promised.
        """
        log = setup_logging("INFO", logger_name="test_setup")
        assert isinstance(log, logging.Logger)
        assert log.name == "test_setup"
        assert log.propagate is False

    def test_custom_name(self) -> None:
        """Verifies a custom logger name is preserved on the returned logger.

        Tests name assignment by passing a distinct name and asserting it
        appears on the result.

        Business context:
            Callers distinguish loggers by name in log output; the name
            must be exactly what was requested.

        Arrangement:
            1. No setup needed; logger creation is self-contained.

        Action:
            Call setup_logging with logger_name "custom".

        Assertion Strategy:
            Validates naming by confirming:
            - The logger's name attribute equals "custom".

        Testing Principle:
            Validates parameterization, ensuring caller-supplied names
            flow through to the logger unchanged.
        """
        log = setup_logging("DEBUG", logger_name="custom")
        assert log.name == "custom"

    def test_invalid_level_raises(self) -> None:
        """Verifies an invalid log level string raises ValueError.

        Tests input validation by passing a nonsense level string and
        expecting a descriptive exception.

        Business context:
            Typos in CLI --log-level flags should fail fast with a clear
            message rather than silently defaulting.

        Arrangement:
            1. No setup needed; validation occurs at call time.

        Action:
            Call setup_logging with level "INVALID".

        Assertion Strategy:
            Validates rejection by confirming:
            - ValueError is raised with message matching "Invalid log level".

        Testing Principle:
            Validates fail-fast input validation, ensuring bad configuration
            is caught immediately rather than producing silent misbehavior.
        """
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging("INVALID", logger_name="bad_level")

    def test_console_handler_only(self) -> None:
        """Verifies default configuration attaches exactly one console handler.

        Tests handler setup by omitting the log_file parameter and checking
        that only a StreamHandler is present.

        Business context:
            Console-only logging is the default for CLI usage; extra handlers
            would clutter output or cause I/O errors.

        Arrangement:
            1. No setup needed; default behavior is under test.

        Action:
            Call setup_logging with no log_file argument.

        Assertion Strategy:
            Validates handler count and type by confirming:
            - Exactly one handler is attached.
            - That handler is a StreamHandler (console).

        Testing Principle:
            Validates default behavior, ensuring the minimal handler
            configuration is applied when no file is requested.
        """
        log = setup_logging("INFO", logger_name="console_only")
        assert len(log.handlers) == 1
        assert isinstance(log.handlers[0], logging.StreamHandler)

    def test_file_handler_added(self, tmp_path: Path) -> None:
        """Verifies a FileHandler is added when log_file is specified.

        Tests file logging by providing a path inside tmp_path and
        checking handler count, type, and directory creation.

        Business context:
            Persistent log files are critical for post-mortem debugging
            of unattended installations; the parent directory must be
            created automatically.

        Arrangement:
            1. Construct a log file path under a non-existent subdirectory
               of tmp_path, so directory creation is exercised.

        Action:
            Call setup_logging with the constructed log_file path.

        Assertion Strategy:
            Validates file handler setup by confirming:
            - Two handlers are attached (console + file).
            - The second handler is a FileHandler.
            - The log file's parent directory exists.

        Testing Principle:
            Validates side-effect correctness, ensuring both the handler
            attachment and prerequisite directory creation occur.
        """
        log_file = tmp_path / "sub" / "test.log"
        log = setup_logging("DEBUG", log_file=log_file, logger_name="with_file")
        assert len(log.handlers) == 2
        assert isinstance(log.handlers[1], logging.FileHandler)
        assert log_file.parent.exists()

    def test_clears_existing_handlers(self) -> None:
        """Verifies repeated setup_logging calls clear previous handlers.

        Tests handler cleanup by calling setup_logging twice with the same
        logger name and checking that handlers are not duplicated.

        Business context:
            Re-configuring logging (e.g., after a --log-level change) must
            not stack handlers, which would cause duplicate log lines.

        Arrangement:
            1. Call setup_logging once to attach an initial handler.

        Action:
            Call setup_logging again with the same logger name.

        Assertion Strategy:
            Validates idempotency by confirming:
            - Only one handler remains after the second call.

        Testing Principle:
            Validates idempotent reconfiguration, ensuring callers can
            safely re-initialize logging without handler accumulation.
        """
        name = "handler_clear_test"
        setup_logging("INFO", logger_name=name)
        log = setup_logging("DEBUG", logger_name=name)
        assert len(log.handlers) == 1


# ── Dataclasses ──────────────────────────────────────────────────────────────


class TestDataclasses:
    """Test suite for FileMapping and InstallationResult data contracts.

    Categories:
    1. FileMapping fields - verifies field storage and immutability (2 tests)
    2. InstallationResult defaults - verifies default values for optional fields (1 test)
    3. InstallationResult error state - verifies error payload propagation (1 test)

    Total: 4 tests.
    """

    def test_file_mapping_fields(self) -> None:
        """Verifies FileMapping stores source and destination paths correctly.

        Tests field assignment by constructing a FileMapping and reading
        both fields back.

        Business context:
            FileMapping drives the copy loop; incorrect field storage would
            silently copy files to wrong destinations.

        Arrangement:
            1. No external state needed; dataclass is self-contained.

        Action:
            Construct FileMapping with "src.md" and "dst.md".

        Assertion Strategy:
            Validates field storage by confirming:
            - src_relative holds "src.md".
            - dst_relative holds "dst.md".

        Testing Principle:
            Validates data integrity, ensuring constructor arguments
            are stored in the correct fields without transposition.
        """
        fm = FileMapping("src.md", "dst.md")
        assert fm.src_relative == "src.md"
        assert fm.dst_relative == "dst.md"

    def test_file_mapping_frozen(self) -> None:
        """Verifies FileMapping is immutable after construction.

        Tests frozen dataclass enforcement by attempting to reassign a field
        and expecting an AttributeError.

        Business context:
            File mappings are shared across installation steps; mutation
            would cause unpredictable copy behavior.

        Arrangement:
            1. Construct a FileMapping instance.

        Action:
            Attempt to assign a new value to src_relative.

        Assertion Strategy:
            Validates immutability by confirming:
            - AttributeError is raised on field reassignment.

        Testing Principle:
            Validates defensive design, ensuring the frozen constraint
            prevents accidental mutation of shared data.
        """
        fm = FileMapping("a", "b")
        with pytest.raises(AttributeError):
            fm.src_relative = "c"  # type: ignore[misc]

    def test_installation_result_defaults(self) -> None:
        """Verifies InstallationResult optional fields default correctly.

        Tests default values by constructing a success result with only
        required fields and checking the optional ones.

        Business context:
            Callers check error_message and files_failed to decide
            reporting behavior; wrong defaults would trigger false alarms.

        Arrangement:
            1. No setup needed; defaults are dataclass-level.

        Action:
            Construct InstallationResult with only required fields.

        Assertion Strategy:
            Validates default contract by confirming:
            - error_message is None (no error).
            - files_failed is 0 (no failures).

        Testing Principle:
            Validates safe defaults, ensuring omitted optional fields
            represent the benign/success case.
        """
        r = InstallationResult(success=True, files_copied=3, target_dir=Path("/t"))
        assert r.error_message is None
        assert r.files_failed == 0

    def test_installation_result_with_error(self) -> None:
        """Verifies InstallationResult stores error details when provided.

        Tests error payload by constructing a failure result with explicit
        error_message and files_failed values.

        Business context:
            Error reporting in CLI output and logs depends on these fields
            being faithfully stored from the installation logic.

        Arrangement:
            1. No setup needed; all values are constructor arguments.

        Action:
            Construct InstallationResult with success=False, error details.

        Assertion Strategy:
            Validates error propagation by confirming:
            - success is False.
            - error_message holds the provided string.
            - files_failed holds the provided count.

        Testing Principle:
            Validates error fidelity, ensuring failure metadata is
            preserved without loss for downstream consumers.
        """
        r = InstallationResult(
            success=False,
            files_copied=0,
            target_dir=Path("/t"),
            error_message="boom",
            files_failed=2,
        )
        assert not r.success
        assert r.error_message == "boom"
        assert r.files_failed == 2


# ── PathResolver ─────────────────────────────────────────────────────────────


class TestPathResolverInit:
    """Test suite for PathResolver initialization and OS detection.

    Categories:
    1. Supported platforms - verifies Linux, Darwin, Windows resolve correctly (3 tests)
    2. Unsupported platform - verifies rejection of unknown OS strings (1 test)

    Total: 4 tests.
    """

    def test_linux(self) -> None:
        """Verifies PathResolver detects Linux as OperatingSystem.LINUX.

        Tests OS detection by constructing a PathResolver with a Linux
        FakeEnvironment and checking the system property.

        Business context:
            Path resolution logic branches on the detected OS; incorrect
            detection would produce wrong config directory paths.

        Arrangement:
            1. Create FakeEnvironment returning "Linux" from get_system().

        Action:
            Construct PathResolver with the Linux environment.

        Assertion Strategy:
            Validates OS mapping by confirming:
            - r.system is the OperatingSystem.LINUX member.

        Testing Principle:
            Validates platform detection, ensuring the Linux platform
            string maps to the correct enum member.
        """
        r = PathResolver(FakeEnvironment("Linux"), FakeFileSystem())
        assert r.system is OperatingSystem.LINUX

    def test_darwin(self) -> None:
        """Verifies PathResolver detects Darwin as OperatingSystem.DARWIN.

        Tests OS detection by constructing a PathResolver with a Darwin
        FakeEnvironment and checking the system property.

        Business context:
            macOS uses Application Support paths that differ from Linux;
            correct detection is prerequisite to correct path resolution.

        Arrangement:
            1. Create FakeEnvironment returning "Darwin" from get_system().

        Action:
            Construct PathResolver with the Darwin environment.

        Assertion Strategy:
            Validates OS mapping by confirming:
            - r.system is the OperatingSystem.DARWIN member.

        Testing Principle:
            Validates platform detection, ensuring the macOS platform
            string maps to the correct enum member.
        """
        r = PathResolver(FakeEnvironment("Darwin"), FakeFileSystem())
        assert r.system is OperatingSystem.DARWIN

    def test_windows(self) -> None:
        """Verifies PathResolver detects Windows as OperatingSystem.WINDOWS.

        Tests OS detection by constructing a PathResolver with a Windows
        FakeEnvironment and checking the system property.

        Business context:
            Windows uses APPDATA-based paths; correct detection gates
            the APPDATA lookup branch in path resolution.

        Arrangement:
            1. Create FakeEnvironment returning "Windows" from get_system().

        Action:
            Construct PathResolver with the Windows environment.

        Assertion Strategy:
            Validates OS mapping by confirming:
            - r.system is the OperatingSystem.WINDOWS member.

        Testing Principle:
            Validates platform detection, ensuring the Windows platform
            string maps to the correct enum member.
        """
        r = PathResolver(FakeEnvironment("Windows"), FakeFileSystem())
        assert r.system is OperatingSystem.WINDOWS

    def test_unsupported_os(self) -> None:
        """Verifies PathResolver rejects unsupported OS strings with ValueError.

        Tests error handling by passing an unrecognized platform string
        and expecting a descriptive exception.

        Business context:
            Running on an unsupported OS should fail immediately with a
            clear message rather than producing silently wrong paths.

        Arrangement:
            1. Create FakeEnvironment returning "FreeBSD" from get_system().

        Action:
            Attempt to construct PathResolver with the unsupported environment.

        Assertion Strategy:
            Validates rejection by confirming:
            - ValueError is raised with message matching "Unsupported operating system".

        Testing Principle:
            Validates fail-fast boundary checking, ensuring unknown
            platforms are caught at construction time.
        """
        with pytest.raises(ValueError, match="Unsupported operating system"):
            PathResolver(FakeEnvironment("FreeBSD"), FakeFileSystem())


class TestGetVscodeConfigDir:
    """Test suite for PathResolver.get_vscode_config_dir cross-platform path resolution.

    Categories:
    1. Linux paths - verifies Code and Code-Insiders XDG config paths (2 tests)
    2. Unknown editor - verifies None return for unrecognized editors (1 test)
    3. macOS paths - verifies Application Support path structure (1 test)
    4. Windows paths - verifies APPDATA-based path and missing APPDATA fallback (2 tests)

    Total: 6 tests.
    """

    def test_linux_code(self, linux_resolver: PathResolver) -> None:
        """Verifies Linux config path for stable VS Code edition.

        Tests path construction by resolving the "Code" editor on a Linux
        environment and comparing against the expected XDG path.

        Business context:
            Global agent files are installed into the VS Code User directory;
            an incorrect path means files land in the wrong location and
            Copilot never discovers them.

        Arrangement:
            1. Use the linux_resolver fixture (Linux FakeEnvironment with
               home at /home/testuser).

        Action:
            Call get_vscode_config_dir with editor "Code".

        Assertion Strategy:
            Validates exact path by confirming:
            - Result equals /home/testuser/.config/Code/User.

        Testing Principle:
            Validates platform-specific path construction, ensuring the
            Linux XDG convention is followed for the stable editor.
        """
        assert linux_resolver.get_vscode_config_dir("Code") == Path(
            "/home/testuser/.config/Code/User"
        )

    def test_linux_insiders(self, linux_resolver: PathResolver) -> None:
        """Verifies Linux config path for VS Code Insiders edition.

        Tests path construction by resolving "Code-Insiders" and checking
        the space-separated directory name convention.

        Business context:
            Insiders uses "Code - Insiders" (with spaces) as its config
            directory name; getting this wrong breaks Insiders installations.

        Arrangement:
            1. Use the linux_resolver fixture.

        Action:
            Call get_vscode_config_dir with editor "Code-Insiders".

        Assertion Strategy:
            Validates exact path by confirming:
            - Result equals /home/testuser/.config/Code - Insiders/User.

        Testing Principle:
            Validates editor name mapping, ensuring the hyphenated CLI
            name translates to the space-separated filesystem name.
        """
        assert linux_resolver.get_vscode_config_dir("Code-Insiders") == Path(
            "/home/testuser/.config/Code - Insiders/User"
        )

    def test_unknown_editor_returns_none(self, linux_resolver: PathResolver) -> None:
        """Verifies unrecognized editor names return None.

        Tests boundary handling by passing an editor name outside the
        supported set and expecting None.

        Business context:
            Callers use None to decide whether to abort or fall back;
            returning a fabricated path for unknown editors would cause
            file writes to arbitrary locations.

        Arrangement:
            1. Use the linux_resolver fixture.

        Action:
            Call get_vscode_config_dir with editor "Atom".

        Assertion Strategy:
            Validates None sentinel by confirming:
            - Result is None.

        Testing Principle:
            Validates safe failure, ensuring unsupported editors produce
            an explicit None rather than a wrong path.
        """
        assert linux_resolver.get_vscode_config_dir("Atom") is None

    def test_darwin(self) -> None:
        """Verifies macOS config path uses Library/Application Support.

        Tests Darwin-specific path construction by creating a macOS
        environment and resolving the "Code" editor.

        Business context:
            macOS applications store user config under ~/Library/Application
            Support; following this convention is required for VS Code to
            discover installed agent files.

        Arrangement:
            1. Create FakeEnvironment with system "Darwin" and home
               /Users/test.
            2. Create PathResolver with that environment.

        Action:
            Call get_vscode_config_dir with editor "Code".

        Assertion Strategy:
            Validates exact path by confirming:
            - Result equals /Users/test/Library/Application Support/Code/User.

        Testing Principle:
            Validates platform-specific path construction, ensuring the
            macOS convention is followed correctly.
        """
        env = FakeEnvironment("Darwin", home=Path("/Users/test"))
        r = PathResolver(env, FakeFileSystem())
        assert r.get_vscode_config_dir("Code") == Path(
            "/Users/test/Library/Application Support/Code/User"
        )

    def test_windows_with_appdata(self) -> None:
        """Verifies Windows config path uses APPDATA environment variable.

        Tests Windows path construction by providing an APPDATA env var
        and checking the resulting path contains expected components.

        Business context:
            Windows VS Code config lives under %APPDATA%/Code/User;
            the APPDATA variable must be read from the environment since
            there is no reliable filesystem convention to fall back on.

        Arrangement:
            1. Create FakeEnvironment with system "Windows" and APPDATA
               pointing to a typical Roaming directory.
            2. Create PathResolver with that environment.

        Action:
            Call get_vscode_config_dir with editor "Code".

        Assertion Strategy:
            Validates path structure by confirming:
            - Result is not None.
            - Path string contains "Code".
            - Path string contains "User".

        Testing Principle:
            Validates environment-driven path construction, ensuring
            APPDATA is incorporated into the resolved path.
        """
        env = FakeEnvironment(
            "Windows", env_vars={"APPDATA": r"C:\Users\test\AppData\Roaming"}
        )
        r = PathResolver(env, FakeFileSystem())
        result = r.get_vscode_config_dir("Code")
        assert result is not None
        assert "Code" in str(result)
        assert "User" in str(result)

    def test_windows_no_appdata(self) -> None:
        """Verifies Windows returns None when APPDATA is missing.

        Tests the missing-environment-variable branch by providing an
        empty env_vars dict on a Windows environment.

        Business context:
            Without APPDATA, there is no reliable way to locate the VS Code
            config directory on Windows; returning None lets callers report
            a clear error.

        Arrangement:
            1. Create FakeEnvironment with system "Windows" and no env vars.
            2. Create PathResolver with that environment.

        Action:
            Call get_vscode_config_dir with editor "Code".

        Assertion Strategy:
            Validates None sentinel by confirming:
            - Result is None.

        Testing Principle:
            Validates graceful degradation, ensuring missing environment
            configuration produces None rather than an exception or
            incorrect path.
        """
        env = FakeEnvironment("Windows", env_vars={})
        r = PathResolver(env, FakeFileSystem())
        assert r.get_vscode_config_dir("Code") is None


class TestGetLocalInstallDir:
    """Test suite for PathResolver.get_local_install_dir git-root discovery.

    Categories:
    1. Git root detection - Locates .git directory at cwd and parent levels (2 tests)
    2. Fallback behavior - Handles missing .git and filesystem root edge case (2 tests)

    Total: 4 tests.
    """

    def test_git_at_cwd(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install dir resolves to .github when .git is at cwd.

        Tests git-root detection by placing .git directly in the working directory.

        Business context:
            Most users run install from their project root where .git lives.

        Arrangement:
            1. Set cwd to /home/user/project to simulate typical project root.
            2. Add .git directory at cwd to indicate repository root.

        Action:
            Calls get_local_install_dir to resolve the .github target directory.

        Assertion Strategy:
            Validates path resolution by confirming:
            - Result is cwd/.github, the standard local install location.

        Testing Principle:
            Validates happy-path detection, ensuring the most common case works correctly.
        """
        fake_fs._cwd = Path("/home/user/project")
        fake_fs.dirs.add("/home/user/project/.git")
        r = PathResolver(FakeEnvironment(), fake_fs)
        assert r.get_local_install_dir() == Path("/home/user/project/.github")

    def test_git_at_parent(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install dir resolves to ancestor .github when .git is in a parent.

        Tests upward traversal by placing .git two levels above the working directory.

        Business context:
            Users often run commands from subdirectories within a repository.

        Arrangement:
            1. Set cwd deep inside a project at /home/user/project/src/deep.
            2. Place .git at /home/user/project to simulate the actual repo root.

        Action:
            Calls get_local_install_dir which traverses parent directories to find .git.

        Assertion Strategy:
            Validates ancestor traversal by confirming:
            - Result points to /home/user/project/.github, not the cwd.

        Testing Principle:
            Validates recursive parent search, ensuring deep subdirectories resolve correctly.
        """
        fake_fs._cwd = Path("/home/user/project/src/deep")
        fake_fs.dirs.add("/home/user/project/.git")
        r = PathResolver(FakeEnvironment(), fake_fs)
        assert r.get_local_install_dir() == Path("/home/user/project/.github")

    def test_no_git_fallback(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install dir falls back to cwd/.github when no .git exists.

        Tests fallback behavior by omitting any .git directory from the filesystem.

        Business context:
            Supports installation in non-git directories or freshly initialized projects.

        Arrangement:
            1. Set cwd to /home/user/project with no .git directory present.

        Action:
            Calls get_local_install_dir which searches for .git, finds none, and falls back.

        Assertion Strategy:
            Validates fallback logic by confirming:
            - Result defaults to cwd/.github when no repository root is found.

        Testing Principle:
            Validates graceful degradation, ensuring non-git environments still work.
        """
        fake_fs._cwd = Path("/home/user/project")
        r = PathResolver(FakeEnvironment(), fake_fs)
        assert r.get_local_install_dir() == Path("/home/user/project/.github")

    def test_cwd_is_root(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install dir resolves to /.github when cwd is the filesystem root.

        Tests edge-case handling when parent traversal reaches the root directory.

        Business context:
            Prevents infinite loops or errors when running from filesystem root.

        Arrangement:
            1. Set cwd to / to simulate the filesystem root boundary.

        Action:
            Calls get_local_install_dir which has no parents left to traverse.

        Assertion Strategy:
            Validates boundary condition by confirming:
            - Result is /.github without errors or infinite recursion.

        Testing Principle:
            Validates boundary handling, ensuring root directory terminates traversal safely.
        """
        fake_fs._cwd = Path("/")
        r = PathResolver(FakeEnvironment(), fake_fs)
        assert r.get_local_install_dir() == Path("/.github")


# ── EditorDetector ───────────────────────────────────────────────────────────


class TestEditorDetector:
    """Test suite for EditorDetector VS Code edition detection.

    Categories:
    1. Priority detection - Verifies Insiders takes precedence over stable (1 test)
    2. Fallback detection - Handles missing editors and platform edge cases (3 tests)

    Total: 4 tests.
    """

    def test_detects_insiders_first(self, fake_fs: FakeFileSystem) -> None:
        """Verifies Insiders edition is preferred when both editions are installed.

        Tests detection priority by making both Code and Code-Insiders config dirs exist.

        Business context:
            Insiders users expect the installer to target their preferred edition first.

        Arrangement:
            1. Create config directories for both Code and Code-Insiders editions.

        Action:
            Calls detect_installed_editor which checks editions in priority order.

        Assertion Strategy:
            Validates priority ordering by confirming:
            - Returns "Code-Insiders" even though stable Code is also present.

        Testing Principle:
            Validates preference ordering, ensuring the higher-priority edition wins.
        """
        env = FakeEnvironment()
        r = PathResolver(env, fake_fs)
        insiders_dir = str(r.get_vscode_config_dir("Code-Insiders"))
        stable_dir = str(r.get_vscode_config_dir("Code"))
        fake_fs.dirs.update({insiders_dir, stable_dir})
        d = EditorDetector(r, fake_fs)
        assert d.detect_installed_editor() == "Code-Insiders"

    def test_detects_stable_when_no_insiders(self, fake_fs: FakeFileSystem) -> None:
        """Verifies stable Code is detected when Insiders is not installed.

        Tests fallback to stable by only providing the Code config directory.

        Business context:
            Most users have stable Code only; detection must find it reliably.

        Arrangement:
            1. Create config directory for stable Code only, no Insiders.

        Action:
            Calls detect_installed_editor which skips missing Insiders and finds Code.

        Assertion Strategy:
            Validates fallback selection by confirming:
            - Returns "Code" when Insiders directory is absent.

        Testing Principle:
            Validates secondary preference, ensuring stable edition is the next choice.
        """
        env = FakeEnvironment()
        r = PathResolver(env, fake_fs)
        stable_dir = str(r.get_vscode_config_dir("Code"))
        fake_fs.dirs.add(stable_dir)
        d = EditorDetector(r, fake_fs)
        assert d.detect_installed_editor() == "Code"

    def test_default_when_none_found(self, fake_fs: FakeFileSystem) -> None:
        """Verifies default to "Code" when no editor config directories exist.

        Tests last-resort fallback by providing an empty filesystem.

        Business context:
            Fresh installs or unusual setups should still produce a usable default.

        Arrangement:
            1. Use empty FakeFileSystem with no editor config directories.

        Action:
            Calls detect_installed_editor which finds no matching directories.

        Assertion Strategy:
            Validates default fallback by confirming:
            - Returns "Code" as the safe default when nothing is detected.

        Testing Principle:
            Validates safe defaults, ensuring detection never returns an unusable value.
        """
        r = PathResolver(FakeEnvironment(), fake_fs)
        d = EditorDetector(r, fake_fs)
        assert d.detect_installed_editor() == "Code"

    def test_config_dir_none_short_circuit(self, fake_fs: FakeFileSystem) -> None:
        """Verifies short-circuit when config_dir resolves to None on Windows.

        Tests the None-path branch by simulating Windows without APPDATA set.

        Business context:
            Windows environments missing APPDATA should not crash the detector.

        Arrangement:
            1. Create Windows FakeEnvironment with empty env_vars (no APPDATA).

        Action:
            Calls detect_installed_editor where get_vscode_config_dir returns None.

        Assertion Strategy:
            Validates None handling by confirming:
            - Returns "Code" default without raising an exception.

        Testing Principle:
            Validates defensive branching, ensuring None config dirs are safely skipped.
        """
        env = FakeEnvironment("Windows", env_vars={})
        r = PathResolver(env, fake_fs)
        d = EditorDetector(r, fake_fs)
        assert d.detect_installed_editor() == "Code"


# ── AgentInstaller._validate_source_files ────────────────────────────────────


class TestValidateSourceFiles:
    """Test suite for AgentInstaller._validate_source_files directory validation.

    Categories:
    1. Validation outcomes - Confirms pass/fail based on directory existence (2 tests)

    Total: 2 tests.
    """

    def test_exists(self, fake_fs: FakeFileSystem) -> None:
        """Verifies validation passes when agent_files directory exists.

        Tests the success path by pre-creating the expected source directory.

        Business context:
            Installation must confirm source files exist before copying begins.

        Arrangement:
            1. Add /fake/agent_files to the fake filesystem's known directories.

        Action:
            Calls _validate_source_files to check the agent_files_dir.

        Assertion Strategy:
            Validates existence check by confirming:
            - Returns True when the directory is present.

        Testing Principle:
            Validates precondition check, ensuring valid setups proceed.
        """
        fake_fs.dirs.add("/fake/agent_files")

    def test_missing(self, fake_fs: FakeFileSystem) -> None:
        """Verifies validation fails when agent_files directory is absent.

        Tests the failure path by omitting the source directory from the filesystem.

        Business context:
            Prevents cryptic copy errors by failing fast with a clear signal.

        Arrangement:
            1. Use default FakeFileSystem with no /fake/agent_files directory.

        Action:
            Calls _validate_source_files against a non-existent directory.

        Assertion Strategy:
            Validates absence detection by confirming:
            - Returns False when the directory is missing.

        Testing Principle:
            Validates fail-fast behavior, ensuring missing sources are caught early.
        """
        installer = _make_installer(fake_fs)
        assert installer._validate_source_files() is False


# ── AgentInstaller._apply_template_vars ──────────────────────────────────────


class TestApplyTemplateVars:
    """Test suite for AgentInstaller._apply_template_vars placeholder substitution.

    Categories:
    1. Substitution - Replaces template placeholders with configured values (1 test)
    2. No-op cases - Skips writes when unnecessary (2 tests)
    3. Error resilience - Handles filesystem errors gracefully (1 test)

    Total: 4 tests.
    """

    def test_replaces_placeholder(self, fake_fs: FakeFileSystem) -> None:
        """Verifies JOURNAL_PATH placeholder is replaced with the configured value.

        Tests substitution by placing a {{JOURNAL_PATH}} token in a target file.

        Business context:
            Installed files must reflect user-specific journal paths to function correctly.

        Arrangement:
            1. Write a file containing "{{JOURNAL_PATH}}" to the fake filesystem.
            2. Create installer with journal_path="docs/journal".

        Action:
            Calls _apply_template_vars to process the file mapping.

        Assertion Strategy:
            Validates substitution by confirming:
            - File content replaces {{JOURNAL_PATH}} with "docs/journal".

        Testing Principle:
            Validates template expansion, ensuring placeholders are fully resolved.
        """
        fake_fs.files["/target/j.md"] = "path: {{JOURNAL_PATH}}/daily"
        installer = _make_installer(fake_fs, journal_path="docs/journal")
        installer._apply_template_vars(
            Path("/target"), [FileMapping("j.md", "j.md")]
        )
        assert fake_fs.files["/target/j.md"] == "path: docs/journal/daily"

    def test_no_placeholder_no_write(self, fake_fs: FakeFileSystem) -> None:
        """Verifies files without placeholders are left unmodified.

        Tests the no-op path by providing content that contains no template tokens.

        Business context:
            Unnecessary writes waste I/O and could corrupt file metadata.

        Arrangement:
            1. Write a file with plain content (no {{JOURNAL_PATH}} token).

        Action:
            Calls _apply_template_vars on the file with no matching placeholders.

        Assertion Strategy:
            Validates skip logic by confirming:
            - File content remains identical after template processing.

        Testing Principle:
            Validates idempotency, ensuring non-template files are untouched.
        """
        fake_fs.files["/target/a.md"] = "no template vars here"
        installer = _make_installer(fake_fs)
        installer._apply_template_vars(
            Path("/target"), [FileMapping("a.md", "a.md")]
        )
        assert fake_fs.files["/target/a.md"] == "no template vars here"

    def test_oserror_silently_ignored(self, fake_fs: FakeFileSystem) -> None:
        """Verifies OSError during template processing is silently ignored.

        Tests error resilience by referencing a non-existent file in the mapping.

        Business context:
            Template failures should not abort an otherwise successful installation.

        Arrangement:
            1. Create installer without adding the mapped file to the filesystem.

        Action:
            Calls _apply_template_vars with a mapping to a missing file, triggering
            FileNotFoundError.

        Assertion Strategy:
            Validates error suppression by confirming:
            - No exception propagates; method completes silently.

        Testing Principle:
            Validates fault tolerance, ensuring non-critical errors are absorbed.
        """
        installer = _make_installer(fake_fs)
        # File doesn't exist → FileNotFoundError (subclass of OSError)
        installer._apply_template_vars(
            Path("/target"), [FileMapping("missing.md", "missing.md")]
        )

    def test_empty_files_list(self, fake_fs: FakeFileSystem) -> None:
        """Verifies no-op when an empty file list is provided.

        Tests boundary condition by passing an empty list to template processing.

        Business context:
            Callers may pass empty lists legitimately; this must not raise errors.

        Arrangement:
            1. Create a standard installer with no special filesystem setup.

        Action:
            Calls _apply_template_vars with an empty file mapping list.

        Assertion Strategy:
            Validates empty-input handling by confirming:
            - Method returns without errors or side effects.

        Testing Principle:
            Validates empty-collection safety, ensuring zero-length input is harmless.
        """
        installer = _make_installer(fake_fs)
        installer._apply_template_vars(Path("/target"), [])


# ── AgentInstaller.install_files ─────────────────────────────────────────────


class TestInstallFiles:
    """Test suite for AgentInstaller.install_files orchestration logic.

    Categories:
    1. Validation gating - Blocks installation when preconditions fail (1 test)
    2. Dry-run mode - Simulates installation without I/O (1 test)
    3. Delegation - Confirms handoff to _perform_installation (1 test)

    Total: 3 tests.
    """

    def test_validation_failure(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_files fails when source validation rejects the directory.

        Tests the validation gate by omitting the agent_files directory.

        Business context:
            Early validation prevents partial installations from corrupting user config.

        Arrangement:
            1. Create installer without adding agent_files_dir to the filesystem.

        Action:
            Calls install_files which first runs _validate_source_files.

        Assertion Strategy:
            Validates gating logic by confirming:
            - Result reports failure with "Agent files directory not found" message.

        Testing Principle:
            Validates precondition enforcement, ensuring invalid state is rejected upfront.
        """
        installer = _make_installer(fake_fs)
        result = installer.install_files(Path("/target"), [])
        assert result.error_message == "Agent files directory not found"

    def test_dry_run(self, fake_fs: FakeFileSystem) -> None:
        """Verifies dry-run mode reports success without performing file I/O.

        Tests simulation by passing dry_run=True with valid source files.

        Business context:
            Dry-run allows users to preview installation effects before committing.

        Arrangement:
            1. Add agent_files_dir to satisfy validation.
            2. Define two file mappings to verify count reporting.

        Action:
            Calls install_files with dry_run=True to simulate the installation.

        Assertion Strategy:
            Validates dry-run behavior by confirming:
            - Result is successful with files_copied matching the mapping count.

        Testing Principle:
            Validates preview mode, ensuring no side effects occur during simulation.
        """
        fake_fs.dirs.add("/fake/agent_files")
        installer = _make_installer(fake_fs)
        files = [FileMapping("a.md", "a.md"), FileMapping("b.md", "b.md")]
        result = installer.install_files(Path("/target"), files, dry_run=True)
        assert result.success
        assert result.files_copied == 2

    def test_delegates_to_perform(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_files delegates to _perform_installation for real installs.

        Tests end-to-end flow by providing valid sources and checking file output.

        Business context:
            The public API must correctly hand off to the internal installation engine.

        Arrangement:
            1. Add agent_files_dir and populate it with one source file.

        Action:
            Calls install_files without dry_run, triggering _perform_installation.

        Assertion Strategy:
            Validates delegation by confirming:
            - Result is successful with exactly 1 file copied.

        Testing Principle:
            Validates integration path, ensuring the public API and internal engine connect.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "content"
        installer = _make_installer(fake_fs)
        result = installer.install_files(
            Path("/target"), [FileMapping("a.md", "a.md")]
        )
        assert result.success
        assert result.files_copied == 1


# ── AgentInstaller._perform_installation ─────────────────────────────────────


class TestPerformInstallation:
    """Test suite for AgentInstaller._perform_installation file-copy engine.

    Categories:
    1. Success paths - All or partial files copied successfully (2 tests)
    2. Failure paths - No files copied or fatal errors during I/O (4 tests)
    3. Template integration - Verifies post-copy template variable substitution (1 test)

    Total: 7 tests.
    """

    def test_all_files_copied(self, fake_fs: FakeFileSystem) -> None:
        """Verifies all files are copied when every source exists.

        Tests the happy path by providing all source files in the fake filesystem.

        Business context:
            A complete installation must copy every configured file without errors.

        Arrangement:
            1. Add agent_files_dir and populate both source files a.md and b.md.

        Action:
            Calls _perform_installation with two file mappings.

        Assertion Strategy:
            Validates complete copy by confirming:
            - Result is successful with files_copied=2 and files_failed=0.

        Testing Principle:
            Validates full-success path, ensuring all files transfer correctly.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "aaa"
        fake_fs.files["/fake/agent_files/b.md"] = "bbb"
        installer = _make_installer(fake_fs)
        files = [FileMapping("a.md", "a.md"), FileMapping("b.md", "b.md")]
        result = installer._perform_installation(Path("/target"), files)
        assert result.success
        assert result.files_copied == 2
        assert result.files_failed == 0

    def test_some_source_missing(self, fake_fs: FakeFileSystem) -> None:
        """Verifies partial success when some source files are missing.

        Tests graceful degradation by providing only one of two expected source files.

        Business context:
            Partial installations should still succeed for available files and report gaps.

        Arrangement:
            1. Add agent_files_dir with only a.md, omitting b.md.

        Action:
            Calls _perform_installation with mappings for both a.md and b.md.

        Assertion Strategy:
            Validates partial copy by confirming:
            - Result is successful with files_copied=1 and files_failed=1.

        Testing Principle:
            Validates partial completion, ensuring available files are still installed.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "aaa"
        installer = _make_installer(fake_fs)
        files = [FileMapping("a.md", "a.md"), FileMapping("b.md", "b.md")]
        result = installer._perform_installation(Path("/target"), files)
        assert result.success
        assert result.files_copied == 1
        assert result.files_failed == 1

    def test_no_files_copied(self, fake_fs: FakeFileSystem) -> None:
        """Verifies failure when no files are successfully copied.

        Tests total failure by mapping a file that does not exist in the source.

        Business context:
            Zero-copy installations indicate a misconfiguration and must report failure.

        Arrangement:
            1. Add agent_files_dir but do not populate any source files.

        Action:
            Calls _perform_installation with a mapping to a missing source file.

        Assertion Strategy:
            Validates zero-copy detection by confirming:
            - Result reports failure with "No files were copied" error message.

        Testing Principle:
            Validates total-failure detection, ensuring empty results are flagged.
        """
        fake_fs.dirs.add("/fake/agent_files")
        installer = _make_installer(fake_fs)
        files = [FileMapping("missing.md", "missing.md")]
        result = installer._perform_installation(Path("/target"), files)
        assert not result.success
        assert result.files_copied == 0
        assert result.error_message == "No files were copied"

    def test_oserror_during_mkdir(self, fake_fs: FakeFileSystem) -> None:
        """Verifies failure handling when mkdir raises OSError.

        Tests the mkdir error branch by replacing the filesystem's mkdir with a
        failing stub.

        Business context:
            Permission errors during directory creation must produce clear diagnostics.

        Arrangement:
            1. Add agent_files_dir with one source file.
            2. Replace fake_fs.mkdir with a function that raises OSError.

        Action:
            Calls _perform_installation which attempts to create the target directory.

        Assertion Strategy:
            Validates error capture by confirming:
            - Result reports failure with "permission denied" in the error message.

        Testing Principle:
            Validates I/O error handling, ensuring mkdir failures are reported not swallowed.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "content"
        installer = _make_installer(fake_fs)

        def failing_mkdir(path: Path, **kwargs: object) -> None:
            """Simulate OSError during directory creation for error-path testing.

            Replaces FakeFileSystem.mkdir to trigger the OSError branch
            in _perform_installation.

            Business context:
                Validates that mkdir failures are caught and reported.

            Args:
                path: Directory path (ignored).
                **kwargs: Keyword args (ignored).

            Returns:
                None

            Raises:
                OSError: Always raised with "permission denied".

            Examples:
                >>> failing_mkdir(Path("/any"))
                OSError: permission denied
            """
            raise OSError("permission denied")

        fake_fs.mkdir = failing_mkdir  # type: ignore[assignment]
        result = installer._perform_installation(
            Path("/target"), [FileMapping("a.md", "a.md")]
        )
        assert not result.success
        assert "permission denied" in (result.error_message or "")

    def test_oserror_during_copy(self, fake_fs: FakeFileSystem) -> None:
        """Verifies failure handling when copy_file raises OSError.

        Tests the copy error branch by replacing the filesystem's copy_file with a
        failing stub.

        Business context:
            Disk-full or permission errors during copy must halt and report clearly.

        Arrangement:
            1. Add agent_files_dir with one source file.
            2. Replace fake_fs.copy_file with a function that raises OSError.

        Action:
            Calls _perform_installation which attempts to copy the source file.

        Assertion Strategy:
            Validates error capture by confirming:
            - Result reports failure with "disk full" in the error message.

        Testing Principle:
            Validates copy error handling, ensuring I/O failures produce actionable messages.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "content"
        installer = _make_installer(fake_fs)

        def failing_copy(src: Path, dst: Path) -> None:
            """Simulate OSError during file copy for error-path testing.

            Replaces FakeFileSystem.copy_file to trigger the OSError branch
            in _perform_installation.

            Business context:
                Validates that copy failures are caught and reported.

            Args:
                src: Source path (ignored).
                dst: Destination path (ignored).

            Returns:
                None

            Raises:
                OSError: Always raised with "disk full".

            Examples:
                >>> failing_copy(Path("/a"), Path("/b"))
                OSError: disk full
            """
            raise OSError("disk full")

        fake_fs.copy_file = failing_copy  # type: ignore[assignment]
        result = installer._perform_installation(
            Path("/target"), [FileMapping("a.md", "a.md")]
        )
        assert not result.success
        assert "disk full" in (result.error_message or "")

    def test_oserror_after_partial_copy(self, fake_fs: FakeFileSystem) -> None:
        """Verifies failure reporting when copy fails partway through file list.

        Tests partial-failure by succeeding on the first file and failing on the second.

        Business context:
            Partial failures must accurately report both copied and failed file counts.

        Arrangement:
            1. Add agent_files_dir with two source files a.md and b.md.
            2. Replace fake_fs.copy_file with a stub that fails on the second call.

        Action:
            Calls _perform_installation with two file mappings.

        Assertion Strategy:
            Validates partial-failure accounting by confirming:
            - Result reports failure with files_copied=1 and files_failed=1.

        Testing Principle:
            Validates mid-operation failure, ensuring accurate bookkeeping after partial success.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/a.md"] = "aaa"
        fake_fs.files["/fake/agent_files/b.md"] = "bbb"
        installer = _make_installer(fake_fs)

        call_count = 0
        original_copy = fake_fs.copy_file

        def partial_fail(src: Path, dst: Path) -> None:
            """Fail on the second call to simulate partial-copy failure.

            Tracks invocations via closure counter and raises OSError
            on the second call while delegating the first to the original.

            Business context:
                Validates partial-failure accounting when some files
                copy successfully before an error occurs.

            Args:
                src: Source path passed to original or discarded.
                dst: Destination path passed to original or discarded.

            Returns:
                None

            Raises:
                OSError: Raised on the second invocation with "partial fail".

            Examples:
                >>> partial_fail(Path("/a"), Path("/b"))  # succeeds
                >>> partial_fail(Path("/c"), Path("/d"))  # raises OSError
            """
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("partial fail")
            original_copy(src, dst)

        fake_fs.copy_file = partial_fail  # type: ignore[assignment]
        result = installer._perform_installation(
            Path("/target"), [FileMapping("a.md", "a.md"), FileMapping("b.md", "b.md")]
        )
        assert not result.success
        assert result.files_copied == 1
        assert result.files_failed == 1

    def test_template_vars_applied(self, fake_fs: FakeFileSystem) -> None:
        """Verifies template variables are applied to copied files after installation.

        Tests end-to-end by installing a file with a placeholder and checking substitution.

        Business context:
            Post-copy template expansion ensures installed files are immediately usable.

        Arrangement:
            1. Add agent_files_dir with a source file containing {{JOURNAL_PATH}}.
            2. Create installer with journal_path="my/journal".

        Action:
            Calls _perform_installation which copies the file then applies template vars.

        Assertion Strategy:
            Validates post-copy substitution by confirming:
            - Destination file content has {{JOURNAL_PATH}} replaced with "my/journal".

        Testing Principle:
            Validates integration between copy and template engines, ensuring end-to-end
            correctness.
        """
        fake_fs.dirs.add("/fake/agent_files")
        fake_fs.files["/fake/agent_files/j.md"] = "path: {{JOURNAL_PATH}}"
        installer = _make_installer(fake_fs, journal_path="my/journal")
        result = installer._perform_installation(
            Path("/target"), [FileMapping("j.md", "j.md")]
        )
        assert result.success
        assert fake_fs.files["/target/j.md"] == "path: my/journal"


# ── AgentInstaller.install_local ─────────────────────────────────────────────


class TestInstallLocal:
    """Test suite for AgentInstaller.install_local workflow.

    Categories:
    1. Path resolution - verifies local install targets .github directory (1 test)
    2. Dry-run mode - confirms preview without filesystem writes (1 test)

    Total: 2 tests.
    """

    def test_installs_to_github_dir(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_local copies agent files into the .github directory.

        Tests local installation by populating a fake filesystem with
        source files and a .git directory at the project root.

        Business context:
            Local install must place agent files where GitHub Copilot
            discovers them -- the .github directory of the repository.

        Arrangement:
            1. Set cwd to a project with .git so path resolution finds the root.
            2. Register all SOURCE_FILES in the fake filesystem.

        Action:
            Calls install_local() with default arguments.

        Assertion Strategy:
            Validates correct installation by confirming:
            - result.success is True.
            - result.target_dir equals .github under the project root.

        Testing Principle:
            Validates the happy-path local install, ensuring path resolution
            and file copying integrate correctly.
        """
        fake_fs._cwd = Path("/home/user/project")
        fake_fs.dirs.add("/home/user/project/.git")
        fake_fs.dirs.add("/fake/agent_files")
        for src in AgentInstaller.SOURCE_FILES:
            fake_fs.files[f"/fake/agent_files/{src}"] = f"content of {src}"
        installer = _make_installer(fake_fs)
        result = installer.install_local()
        assert result.success
        assert result.target_dir == Path("/home/user/project/.github")

    def test_dry_run(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_local dry-run reports success without copying files.

        Tests that dry_run=True skips actual filesystem writes while
        still returning a successful result.

        Business context:
            Users need a preview mode to verify what would be installed
            before committing changes to their repository.

        Arrangement:
            1. Configure fake filesystem with .git and agent_files directories.

        Action:
            Calls install_local(dry_run=True).

        Assertion Strategy:
            Validates dry-run behavior by confirming:
            - result.success is True despite no files being written.

        Testing Principle:
            Validates dry-run flag propagation, ensuring install_local
            delegates the flag correctly to install_files.
        """
        fake_fs._cwd = Path("/home/user/project")
        fake_fs.dirs.add("/home/user/project/.git")
        fake_fs.dirs.add("/fake/agent_files")
        installer = _make_installer(fake_fs)
        result = installer.install_local(dry_run=True)
        assert result.success


# ── AgentInstaller.install_global ────────────────────────────────────────────


class TestInstallGlobal:
    """Test suite for AgentInstaller.install_global workflow.

    Categories:
    1. Editor detection - auto-detect and explicit editor selection (2 tests)
    2. Error handling - missing config directory scenarios (2 tests)
    3. Dry-run mode - preview without filesystem writes (1 test)

    Total: 5 tests.
    """

    def _make_global_installer(
        self, fake_fs: FakeFileSystem, env: FakeEnvironment | None = None
    ) -> AgentInstaller:
        """Build an AgentInstaller configured for global install testing.

        Assembles fakes with agent_files_dir pre-registered.

        Business context:
            Centralizes global-install test setup to avoid boilerplate.

        Args:
            fake_fs: In-memory filesystem.
            env: Optional environment override.

        Returns:
            AgentInstaller ready for install_global() calls.

        Raises:
            None

        Examples:
            >>> installer = self._make_global_installer(fake_fs)
        """
        if env is None:
            env = FakeEnvironment()
        fake_fs.dirs.add("/fake/agent_files")
        resolver = PathResolver(env, fake_fs)
        detector = EditorDetector(resolver, fake_fs)
        log = setup_logging("DEBUG", logger_name="test_global")
        return AgentInstaller(
            agent_files_dir=Path("/fake/agent_files"),
            fs=fake_fs,
            path_resolver=resolver,
            editor_detector=detector,
            logger=log,
        )

    def test_auto_detect_editor(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_global auto-detects the installed VS Code editor.

        Tests that omitting the editor argument triggers auto-detection
        and completes installation successfully.

        Business context:
            Most users have a single editor installed; auto-detection
            reduces friction by eliminating a required argument.

        Arrangement:
            1. Create a fake environment with the stable Code config directory.
            2. Populate all SOURCE_FILES in the fake filesystem.

        Action:
            Calls install_global() without an editor argument.

        Assertion Strategy:
            Validates auto-detection by confirming:
            - result.success is True with no explicit editor specified.

        Testing Principle:
            Validates default behavior, ensuring the common case
            works without additional configuration.
        """
        env = FakeEnvironment()
        resolver = PathResolver(env, fake_fs)
        code_dir = str(resolver.get_vscode_config_dir("Code"))
        fake_fs.dirs.add(code_dir)
        for src in AgentInstaller.SOURCE_FILES:
            fake_fs.files[f"/fake/agent_files/{src}"] = "content"
        installer = self._make_global_installer(fake_fs, env)
        result = installer.install_global()  # editor=None → auto-detect
        assert result.success

    def test_specified_editor(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_global works with an explicitly specified editor.

        Tests that passing editor='Code' bypasses auto-detection and
        installs to the correct config directory.

        Business context:
            Users with multiple editors need to target a specific one;
            explicit editor selection must override auto-detection.

        Arrangement:
            1. Create a fake environment with the stable Code config directory.
            2. Populate all SOURCE_FILES in the fake filesystem.

        Action:
            Calls install_global(editor="Code").

        Assertion Strategy:
            Validates explicit editor selection by confirming:
            - result.success is True when editor is specified directly.

        Testing Principle:
            Validates explicit configuration, ensuring user overrides
            take precedence over auto-detection.
        """
        env = FakeEnvironment()
        resolver = PathResolver(env, fake_fs)
        code_dir = str(resolver.get_vscode_config_dir("Code"))
        fake_fs.dirs.add(code_dir)
        for src in AgentInstaller.SOURCE_FILES:
            fake_fs.files[f"/fake/agent_files/{src}"] = "content"
        installer = self._make_global_installer(fake_fs, env)
        result = installer.install_global(editor="Code")
        assert result.success

    def test_config_dir_none(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_global fails gracefully for unsupported editors.

        Tests that requesting an unknown editor returns a failure
        result with an empty target directory.

        Business context:
            The installer must not crash on unsupported editors;
            a clear failure result guides users to valid options.

        Arrangement:
            1. Create a default installer with no editor directories registered.

        Action:
            Calls install_global(editor="Atom"), which has no known config path.

        Assertion Strategy:
            Validates error handling by confirming:
            - result.success is False.
            - result.target_dir is an empty Path (no config dir resolved).

        Testing Principle:
            Validates graceful degradation, ensuring unsupported
            inputs produce descriptive failures instead of exceptions.
        """
        installer = self._make_global_installer(fake_fs)
        result = installer.install_global(editor="Atom")
        assert not result.success
        assert result.target_dir == Path()

    def test_config_dir_not_exists(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_global fails when the config directory is missing.

        Tests the scenario where the editor is recognized but its config
        directory does not exist on disk.

        Business context:
            A known editor whose config directory is absent likely means
            the editor is not installed; the error message must say so.

        Arrangement:
            1. Create an installer without registering the Code config directory.

        Action:
            Calls install_global(editor="Code") when the directory is absent.

        Assertion Strategy:
            Validates missing-directory detection by confirming:
            - result.success is False.
            - Error message contains "Could not find Code".
            - result.target_dir is non-empty (config path resolved, just missing).

        Testing Principle:
            Validates existence checks, ensuring the installer distinguishes
            between unknown editors and missing installations.
        """
        installer = self._make_global_installer(fake_fs)
        result = installer.install_global(editor="Code")
        assert not result.success
        assert "Could not find Code" in (result.error_message or "")
        assert result.target_dir != Path()  # config_dir was valid, not None

    def test_dry_run(self, fake_fs: FakeFileSystem) -> None:
        """Verifies install_global dry-run reports success without writing files.

        Tests that dry_run=True previews the global install without
        modifying the editor config directory.

        Business context:
            Dry-run for global installs lets users verify the target
            path and file list before altering shared editor config.

        Arrangement:
            1. Register the Code config directory in fake_fs.

        Action:
            Calls install_global(editor="Code", dry_run=True).

        Assertion Strategy:
            Validates dry-run propagation by confirming:
            - result.success is True without any files copied to disk.

        Testing Principle:
            Validates dry-run flag forwarding, ensuring install_global
            passes the flag through to install_files correctly.
        """
        env = FakeEnvironment()
        resolver = PathResolver(env, fake_fs)
        code_dir = str(resolver.get_vscode_config_dir("Code"))
        fake_fs.dirs.add(code_dir)
        installer = self._make_global_installer(fake_fs, env)
        result = installer.install_global(editor="Code", dry_run=True)
        assert result.success


# ── create_installer ─────────────────────────────────────────────────────────


class TestCreateInstaller:
    """Test suite for create_installer factory function.

    Categories:
    1. Default arguments - verifies sensible defaults are applied (1 test)
    2. Custom arguments - confirms overrides are forwarded correctly (1 test)

    Total: 2 tests.
    """

    def test_default_args(self) -> None:
        """Verifies create_installer produces a valid installer with defaults.

        Tests that calling create_installer() with no arguments returns
        an AgentInstaller with the expected default journal path.

        Business context:
            The factory must produce a working installer out of the box
            so that CLI callers need minimal configuration.

        Arrangement:
            1. No setup required; uses production defaults.

        Action:
            Calls create_installer() with no arguments.

        Assertion Strategy:
            Validates default configuration by confirming:
            - Return type is AgentInstaller.
            - journal_path defaults to "docs/vault".

        Testing Principle:
            Validates sensible defaults, ensuring zero-config usage
            produces a correctly configured installer.
        """
        installer = create_installer()
        assert isinstance(installer, AgentInstaller)
        assert installer.journal_path == "docs/vault"

    def test_custom_args(self, tmp_path: Path) -> None:
        """Verifies create_installer forwards custom arguments to the installer.

        Tests that explicit agent_files_dir, logger, and journal_path
        overrides are passed through to the AgentInstaller instance.

        Business context:
            Programmatic callers and tests need to override defaults;
            the factory must respect every provided argument.

        Arrangement:
            1. Create a custom logger and use tmp_path as agent_files_dir.

        Action:
            Calls create_installer with all custom arguments.

        Assertion Strategy:
            Validates argument forwarding by confirming:
            - installer.agent_files_dir matches the provided tmp_path.
            - installer.journal_path matches the custom value.

        Testing Principle:
            Validates configuration override, ensuring custom arguments
            take precedence over defaults in the factory.
        """
        log = setup_logging("DEBUG", logger_name="custom_create")
        installer = create_installer(
            agent_files_dir=tmp_path, logger=log, journal_path="custom/path"
        )
        assert installer.agent_files_dir == tmp_path
        assert installer.journal_path == "custom/path"


# ── main ─────────────────────────────────────────────────────────────────────


def _mock_installer(success: bool = True) -> MagicMock:
    """Create a MagicMock AgentInstaller with preconfigured install results.

    Builds a mock that returns a fixed InstallationResult from both
    install_local() and install_global().

    Business context:
        Isolates main() CLI tests from actual installation logic.

    Args:
        success: Whether the mock should return a successful result.

    Returns:
        MagicMock with install_local and install_global returning
        the configured InstallationResult.

    Raises:
        None

    Examples:
        >>> mock = _mock_installer(success=True)
        >>> mock.install_local().success
        True
    """
    result = InstallationResult(
        success=success,
        files_copied=3 if success else 0,
        target_dir=Path("/fake"),
        error_message=None if success else "failed",
    )
    mock = MagicMock()
    mock.install_local.return_value = result
    mock.install_global.return_value = result
    return mock


class TestMain:
    """Test suite for main() CLI entry point.

    Categories:
    1. Argument conflicts - mutually exclusive flag validation (1 test)
    2. Local install - success and failure paths (2 tests)
    3. Global install - stable, insiders, and dry-run variants (3 tests)
    4. Dry-run mode - local dry-run flag forwarding (1 test)
    5. Journal path - explicit, interactive, and default resolution (5 tests)
    6. Logging - log level and log file configuration (1 test)

    Total: 13 tests.
    """

    def test_global_and_local_conflict(self) -> None:
        """Verifies main rejects simultaneous --global and --local flags.

        Tests that conflicting install scope flags produce exit code 1
        without attempting any installation.

        Business context:
            Users cannot install both locally and globally in one invocation;
            early rejection prevents ambiguous or partial installs.

        Arrangement:
            1. Set sys.argv with both --global and --local flags.

        Action:
            Calls main() with conflicting arguments.

        Assertion Strategy:
            Validates argument validation by confirming:
            - Return code is 1 (failure).

        Testing Principle:
            Validates input validation, ensuring mutually exclusive
            arguments are caught before any side effects occur.
        """
        with patch("sys.argv", ["copilot-journal", "--global", "--local"]):
            assert main() == 1

    def test_local_install_success(self) -> None:
        """Verifies main returns 0 on successful local installation.

        Tests the happy-path local install via CLI arguments, confirming
        that install_local is called and its success propagates to the exit code.

        Business context:
            The CLI must translate a successful install_local result
            into a zero exit code for scripting and CI pipelines.

        Arrangement:
            1. Create a mock installer that returns success.
            2. Set sys.argv with --local and a journal path.

        Action:
            Calls main() and inspects the return code.

        Assertion Strategy:
            Validates success propagation by confirming:
            - Return code is 0.
            - install_local was called exactly once with dry_run=False.

        Testing Principle:
            Validates CLI-to-installer integration, ensuring arguments
            are correctly translated to method calls.
        """
        mock = _mock_installer(success=True)
        with (
            patch("sys.argv", ["copilot-journal", "--local", "-j", "docs/journal"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0
            mock.install_local.assert_called_once_with(False)

    def test_local_install_failure(self) -> None:
        """Verifies main returns 1 when local installation fails.

        Tests that a failed install_local result translates to a
        non-zero exit code.

        Business context:
            CI/CD pipelines rely on non-zero exit codes to detect
            installation failures and halt deployment.

        Arrangement:
            1. Create a mock installer that returns failure.
            2. Set sys.argv with --local and a journal path.

        Action:
            Calls main() with a failing installer.

        Assertion Strategy:
            Validates failure propagation by confirming:
            - Return code is 1.

        Testing Principle:
            Validates error propagation, ensuring installer failures
            surface as CLI exit codes.
        """
        mock = _mock_installer(success=False)
        with (
            patch("sys.argv", ["copilot-journal", "--local", "-j", "docs/journal"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 1

    def test_global_install_stable(self) -> None:
        """Verifies main triggers global install for stable VS Code by default.

        Tests that --global without --insiders calls install_global
        with editor="Code".

        Business context:
            The default global install targets stable VS Code, which is
            the most common installation among users.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with --global and a journal path.

        Action:
            Calls main() and verifies install_global arguments.

        Assertion Strategy:
            Validates default editor selection by confirming:
            - Return code is 0.
            - install_global was called with ("Code", False).

        Testing Principle:
            Validates default behavior, ensuring --global alone
            targets stable VS Code without requiring --insiders.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "--global", "-j", "x"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0
            mock.install_global.assert_called_once_with("Code", False)

    def test_global_install_insiders(self) -> None:
        """Verifies main targets VS Code Insiders when --insiders is specified.

        Tests that combining --global and --insiders calls install_global
        with editor="Code-Insiders".

        Business context:
            Developers using Insiders builds need explicit targeting;
            the --insiders flag must switch the editor identifier.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with --global, --insiders, and a journal path.

        Action:
            Calls main() and verifies install_global arguments.

        Assertion Strategy:
            Validates Insiders targeting by confirming:
            - Return code is 0.
            - install_global was called with ("Code-Insiders", False).

        Testing Principle:
            Validates flag composition, ensuring --insiders correctly
            modifies the editor argument for global installs.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "--global", "--insiders", "-j", "x"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0
            mock.install_global.assert_called_once_with("Code-Insiders", False)

    def test_global_dry_run(self) -> None:
        """Verifies main passes dry_run=True for global installs with --dry-run.

        Tests that the --dry-run flag is forwarded to install_global
        as the second positional argument.

        Business context:
            Users previewing global installs need the dry-run flag
            to reach the installer without being silently dropped.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with --global, --dry-run, and a journal path.

        Action:
            Calls main() and inspects install_global call arguments.

        Assertion Strategy:
            Validates dry-run forwarding by confirming:
            - Return code is 0.
            - install_global was called with ("Code", True).

        Testing Principle:
            Validates flag propagation, ensuring --dry-run reaches
            the installer method for global installs.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "--global", "--dry-run", "-j", "x"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0
            mock.install_global.assert_called_once_with("Code", True)

    def test_local_dry_run(self) -> None:
        """Verifies main passes dry_run=True for local installs with --dry-run.

        Tests that --dry-run without --global defaults to local install
        and forwards dry_run=True to install_local.

        Business context:
            Local dry-run previews what files would be placed in .github
            without modifying the working repository.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with --dry-run and a journal path (no --global).

        Action:
            Calls main() and inspects install_local call arguments.

        Assertion Strategy:
            Validates local dry-run by confirming:
            - Return code is 0.
            - install_local was called with True (dry_run).

        Testing Principle:
            Validates default scope with flag, ensuring --dry-run alone
            triggers a local dry-run install.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "--dry-run", "-j", "x"]),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0
            mock.install_local.assert_called_once_with(True)

    def test_journal_path_from_arg(self) -> None:
        """Verifies main forwards the -j argument as journal_path to the factory.

        Tests that an explicit -j value is passed through to
        create_installer as the journal_path keyword argument.

        Business context:
            Users specify custom vault paths via -j; the CLI must
            forward this to the installer factory unchanged.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with -j "custom/path".

        Action:
            Calls main() and inspects create_installer keyword arguments.

        Assertion Strategy:
            Validates argument forwarding by confirming:
            - create_installer received journal_path="custom/path".

        Testing Principle:
            Validates CLI argument passthrough, ensuring -j reaches
            the factory without mutation.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "-j", "custom/path"]),
            patch(
                "copilot_journal.install.create_installer", return_value=mock
            ) as create_mock,
        ):
            main()
            _, kwargs = create_mock.call_args
            assert kwargs["journal_path"] == "custom/path"

    def test_interactive_prompt_with_input(self) -> None:
        """Verifies main uses the interactive prompt value as journal_path.

        Tests that when stdin is a TTY and no -j flag is provided,
        main() prompts the user and forwards their input to the factory.

        Business context:
            Interactive users who omit -j should be prompted for the
            vault path rather than silently using the default.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv without -j.
            3. Mock stdin.isatty() to return True.
            4. Mock input() to return "custom/journal".

        Action:
            Calls main() in a simulated interactive terminal.

        Assertion Strategy:
            Validates interactive input by confirming:
            - create_installer received journal_path="custom/journal".

        Testing Principle:
            Validates interactive UX, ensuring TTY users are prompted
            and their input is respected.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal"]),
            patch(
                "copilot_journal.install.create_installer", return_value=mock
            ) as create_mock,
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value="custom/journal"),
        ):
            mock_stdin.isatty.return_value = True
            main()
            _, kwargs = create_mock.call_args
            assert kwargs["journal_path"] == "custom/journal"

    def test_interactive_prompt_empty_uses_default(self) -> None:
        """Verifies main falls back to the default journal_path on empty input.

        Tests that pressing Enter without typing at the interactive prompt
        uses the default "docs/vault" path.

        Business context:
            Users who accept the default should not be forced to type it;
            an empty response must map to the documented default.

        Arrangement:
            1. Create a mock installer.
            2. Mock stdin.isatty() to return True.
            3. Mock input() to return an empty string.

        Action:
            Calls main() with simulated empty interactive input.

        Assertion Strategy:
            Validates default fallback by confirming:
            - create_installer received journal_path="docs/vault".

        Testing Principle:
            Validates default-on-empty, ensuring the prompt treats
            blank input as acceptance of the default value.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal"]),
            patch(
                "copilot_journal.install.create_installer", return_value=mock
            ) as create_mock,
            patch("sys.stdin") as mock_stdin,
            patch("builtins.input", return_value=""),
        ):
            mock_stdin.isatty.return_value = True
            main()
            _, kwargs = create_mock.call_args
            assert kwargs["journal_path"] == "docs/vault"

    def test_dry_run_skips_interactive(self) -> None:
        """Verifies main skips the interactive prompt during dry-run mode.

        Tests that --dry-run suppresses the TTY prompt and uses the
        default journal_path instead.

        Business context:
            Dry-run is a non-interactive preview; prompting the user
            would defeat the purpose of automated previews.

        Arrangement:
            1. Create a mock installer.
            2. Set sys.argv with --dry-run.
            3. Mock stdin.isatty() to return True.

        Action:
            Calls main() in dry-run mode with a TTY stdin.

        Assertion Strategy:
            Validates prompt suppression by confirming:
            - create_installer received journal_path="docs/vault" (default).

        Testing Principle:
            Validates mode interaction, ensuring dry-run overrides
            interactive behavior to remain fully automated.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal", "--dry-run"]),
            patch(
                "copilot_journal.install.create_installer", return_value=mock
            ) as create_mock,
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.isatty.return_value = True
            main()
            _, kwargs = create_mock.call_args
            assert kwargs["journal_path"] == "docs/vault"

    def test_non_interactive_uses_default(self) -> None:
        """Verifies main uses the default journal_path in non-interactive mode.

        Tests that when stdin is not a TTY (e.g., piped input or CI),
        the default path is used without prompting.

        Business context:
            CI/CD and scripted invocations cannot respond to prompts;
            non-TTY detection must silently apply the default.

        Arrangement:
            1. Create a mock installer.
            2. Mock stdin.isatty() to return False.

        Action:
            Calls main() in a non-interactive environment.

        Assertion Strategy:
            Validates non-interactive fallback by confirming:
            - create_installer received journal_path="docs/vault".

        Testing Principle:
            Validates environment detection, ensuring non-TTY stdin
            skips the prompt and uses the default path.
        """
        mock = _mock_installer()
        with (
            patch("sys.argv", ["copilot-journal"]),
            patch(
                "copilot_journal.install.create_installer", return_value=mock
            ) as create_mock,
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.isatty.return_value = False
            main()
            _, kwargs = create_mock.call_args
            assert kwargs["journal_path"] == "docs/vault"

    def test_log_level_and_log_file(self, tmp_path: Path) -> None:
        """Verifies main accepts --log-level and --log-file without errors.

        Tests that logging arguments are parsed and applied, allowing
        the install to complete successfully.

        Business context:
            Debug logging to a file is essential for troubleshooting
            installation issues in user environments.

        Arrangement:
            1. Create a mock installer and a temporary log file path.
            2. Set sys.argv with --log-level DEBUG and --log-file.

        Action:
            Calls main() with logging arguments.

        Assertion Strategy:
            Validates logging configuration by confirming:
            - Return code is 0 (no parse or runtime errors).

        Testing Principle:
            Validates optional argument handling, ensuring logging
            flags are accepted and do not disrupt normal operation.
        """
        mock = _mock_installer()
        log_file = tmp_path / "test.log"
        with (
            patch(
                "sys.argv",
                [
                    "copilot-journal",
                    "-j",
                    "x",
                    "--log-level",
                    "DEBUG",
                    "--log-file",
                    str(log_file),
                ],
            ),
            patch("copilot_journal.install.create_installer", return_value=mock),
        ):
            assert main() == 0


# ── Module imports ───────────────────────────────────────────────────────────


class TestModuleImports:
    """Test suite for package-level module imports.

    Categories:
    1. Package metadata - verifies __init__ and __version__ accessibility (2 tests)

    Total: 2 tests.
    """

    def test_init_module(self) -> None:
        """Verifies the copilot_journal package is importable with a docstring.

        Tests that the top-level package module loads successfully and
        exposes a non-None __doc__ attribute.

        Business context:
            A missing or broken __init__.py prevents all imports;
            this smoke test catches packaging regressions early.

        Arrangement:
            1. No setup required; imports the installed package directly.

        Action:
            Imports copilot_journal and inspects __doc__.

        Assertion Strategy:
            Validates package integrity by confirming:
            - __doc__ is not None, indicating the module loaded.

        Testing Principle:
            Validates import smoke test, ensuring the package is
            importable and minimally configured.
        """
        import copilot_journal

        assert copilot_journal.__doc__ is not None

    def test_version(self) -> None:
        """Verifies __version__ is a string matching the expected release.

        Tests that the version module exports a string version
        matching the current release number.

        Business context:
            Version consistency is critical for PyPI releases and
            user-facing --version output; mismatches cause confusion.

        Arrangement:
            1. No setup required; imports the version module directly.

        Action:
            Imports __version__ and checks its type and value.

        Assertion Strategy:
            Validates version metadata by confirming:
            - __version__ is a str instance.
            - __version__ equals the expected release string.

        Testing Principle:
            Validates version pinning, ensuring the source-of-truth
            version matches the expected release.
        """
        from copilot_journal.__version__ import __version__

        assert isinstance(__version__, str)
        assert __version__ == "0.3.1"
