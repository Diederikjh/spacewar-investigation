#!/usr/bin/env python3

"""Launch and drive one focus-verified ghost-rendering capture session."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid


PROJECT_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = PROJECT_DIR / "analysis/work/ghost-capture"
STATE_FILE = STATE_DIR / "session.json"
PID_FILE = STATE_DIR / "dosbox.pid"
INPUT_HELPER = PROJECT_DIR / "analysis/scripts/x11-input.py"
DEBUG_SCRIPT = "analysis/scripts/phase3-dosbox-debug.sh"
TERMINAL_TITLE_PREFIX = "Spacewar ghost capture"


class SessionError(RuntimeError):
    pass


def relative_source(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("source must be a repository-relative path")
    resolved = (PROJECT_DIR / path).resolve()
    try:
        resolved.relative_to(PROJECT_DIR)
    except ValueError as error:
        raise argparse.ArgumentTypeError("source must remain inside the repository") from error
    if not resolved.is_file():
        raise argparse.ArgumentTypeError(f"source does not exist: {value}")
    return path.as_posix()


def hex_segment(value: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{1,4}", value):
        raise argparse.ArgumentTypeError("segment must contain one to four hex digits")
    return f"{int(value, 16):04x}"


def breakpoint_number(value: str) -> int:
    try:
        number = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("breakpoint number must be decimal") from error
    if number < 0:
        raise argparse.ArgumentTypeError("breakpoint number must not be negative")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manage one ignored DOSBox debugger session and reacquire verified X11 "
            "focus before every runbook input action."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    launch = commands.add_parser("launch", help="launch and discover one session")
    launch.add_argument(
        "--source",
        type=relative_source,
        default="analysis/work/Spacewar1985.exe",
        help="repository-relative executable source",
    )

    commands.add_parser("status", help="validate and show the active session")
    focus = commands.add_parser("focus", help="bring one session window forward")
    focus.add_argument("target", choices=("dosbox", "debugger"))

    commands.add_parser(
        "open-debugger", help="focus DOSBox and send Alt+Pause"
    )
    commands.add_parser(
        "type-breakpoint", help="type BPINT 3 without pressing Enter"
    )
    commands.add_parser(
        "submit-debugger", help="focus the debugger and press Return"
    )
    commands.add_parser("resume-debugger", help="focus the debugger and press F5")
    commands.add_parser(
        "type-breakpoint-list", help="type BPLIST without pressing Enter"
    )

    restore = commands.add_parser(
        "type-restore-entry", help="type the guarded entry restoration command"
    )
    restore.add_argument("cs", type=hex_segment)

    delete = commands.add_parser(
        "type-delete-breakpoint", help="type BPDEL without pressing Enter"
    )
    delete.add_argument("number", type=breakpoint_number)

    data_dump = commands.add_parser(
        "type-data-dump", help="type the bounded data dump without pressing Enter"
    )
    data_dump.add_argument("ds", type=hex_segment)

    commands.add_parser(
        "type-cga-dump", help="type the bounded CGA dump without pressing Enter"
    )

    guest_key = commands.add_parser(
        "guest-key", help="focus DOSBox and send one named X11 key"
    )
    guest_key.add_argument("key")

    commands.add_parser(
        "close", help="terminate the exact active disposable DOSBox session"
    )
    commands.add_parser(
        "cleanup", help="remove state only after its session is no longer valid"
    )
    return parser


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=PROJECT_DIR,
            env=env,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as error:
        raise SessionError(f"required command is unavailable: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or "command failed"
        raise SessionError(detail) from error


def xprop_path() -> str:
    result = shutil.which("xprop", path=os.defpath)
    if not result:
        raise SessionError("required X11 window-property command is unavailable")
    return result


def client_window_ids() -> list[int]:
    executable = xprop_path()
    for property_name in ("_NET_CLIENT_LIST_STACKING", "_NET_CLIENT_LIST"):
        result = run_command([executable, "-root", property_name], check=False)
        if result.returncode == 0:
            values = [int(value, 16) for value in re.findall(r"0x[0-9a-fA-F]+", result.stdout)]
            if values:
                return values
    raise SessionError("cannot read the X11 client-window list")


def window_properties(window: int) -> dict[str, object]:
    result = run_command(
        [
            xprop_path(),
            "-id",
            f"0x{window:x}",
            "_NET_WM_PID",
            "_NET_WM_NAME",
            "WM_NAME",
            "WM_CLASS",
        ],
        check=False,
    )
    if result.returncode != 0:
        return {}

    pid_match = re.search(r"_NET_WM_PID[^=]*=\s*(\d+)", result.stdout)
    quoted = re.findall(r'^(_NET_WM_NAME|WM_NAME)[^=]*=\s*"(.*)"$', result.stdout, re.MULTILINE)
    class_match = re.search(r'^WM_CLASS[^=]*=\s*(.*)$', result.stdout, re.MULTILINE)
    names = {name: value for name, value in quoted}
    return {
        "pid": int(pid_match.group(1)) if pid_match else None,
        "names": names,
        "class": class_match.group(1) if class_match else "",
    }


def window_name(properties: dict[str, object]) -> str:
    names = properties.get("names")
    if not isinstance(names, dict):
        return ""
    return str(names.get("_NET_WM_NAME") or names.get("WM_NAME") or "")


def discover_windows(dosbox_pid: int, terminal_title: str) -> tuple[int, int]:
    dosbox_matches: list[int] = []
    terminal_matches: list[int] = []
    for window in client_window_ids():
        properties = window_properties(window)
        if properties.get("pid") == dosbox_pid and "dosbox-debug" in str(
            properties.get("class", "")
        ).casefold():
            dosbox_matches.append(window)
        if window_name(properties) == terminal_title:
            terminal_matches.append(window)

    if len(dosbox_matches) != 1:
        raise SessionError(
            f"expected one DOSBox window for the launched process; found {len(dosbox_matches)}"
        )
    if len(terminal_matches) != 1:
        raise SessionError(
            f"expected one debugger terminal with the session title; found {len(terminal_matches)}"
        )
    return dosbox_matches[0], terminal_matches[0]


def read_pid_file(deadline: float) -> int:
    while time.monotonic() < deadline:
        try:
            value = PID_FILE.read_text(encoding="ascii").strip()
            pid = int(value, 10)
            if pid > 0:
                return pid
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(0.1)
    raise SessionError("debugger process identity was not reported before timeout")


def write_state(state: dict[str, object]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_DIR / f"session-{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(STATE_FILE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_state() -> dict[str, object]:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SessionError("no active capture session; run launch first") from error
    except (json.JSONDecodeError, OSError) as error:
        raise SessionError("capture session state is unreadable") from error

    required = {
        "session_id": str,
        "source": str,
        "source_sha256": str,
        "terminal_title": str,
        "dosbox_pid": int,
        "dosbox_window": int,
        "debugger_window": int,
    }
    for key, expected_type in required.items():
        if not isinstance(state.get(key), expected_type):
            raise SessionError(f"capture session state has an invalid {key}")
    return state


def pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def validate_state(state: dict[str, object]) -> None:
    pid = int(state["dosbox_pid"])
    if not pid_is_live(pid):
        raise SessionError("capture session process is no longer running")

    dosbox_window = int(state["dosbox_window"])
    debugger_window = int(state["debugger_window"])
    dosbox_properties = window_properties(dosbox_window)
    debugger_properties = window_properties(debugger_window)
    if (
        dosbox_properties.get("pid") != pid
        or "dosbox-debug" not in str(dosbox_properties.get("class", "")).casefold()
    ):
        raise SessionError("stored DOSBox window no longer belongs to this session")
    if window_name(debugger_properties) != state["terminal_title"]:
        raise SessionError("stored debugger window no longer belongs to this session")


def launch(source: str) -> None:
    if STATE_FILE.exists():
        try:
            validate_state(read_state())
        except SessionError as error:
            raise SessionError(
                f"stale session state exists ({error}); run cleanup before launch"
            ) from error
        raise SessionError("an active capture session already exists")

    display = os.environ.get("DISPLAY")
    bus = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if not display or not bus:
        raise SessionError("the active X11 desktop session is unavailable")

    terminal = shutil.which("gnome-terminal", path=os.defpath)
    shell = shutil.which("bash", path=os.defpath)
    if not terminal or not shell:
        raise SessionError("the capture terminal launcher is unavailable")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.unlink(missing_ok=True)
    session_id = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    terminal_title = f"{TERMINAL_TITLE_PREFIX} {session_id}"
    environment = {
        "DISPLAY": display,
        "DBUS_SESSION_BUS_ADDRESS": bus,
        "PATH": os.defpath,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "SPACEWAR_DEBUG_SOURCE": source,
        "SPACEWAR_DEBUG_PID_FILE": PID_FILE.relative_to(PROJECT_DIR).as_posix(),
    }
    for name in ("XAUTHORITY", "SPACEWAR_DOSBOX_DEBUG_BIN"):
        if name in os.environ:
            environment[name] = os.environ[name]

    pid: int | None = None
    try:
        run_command(
            [terminal, "--title", terminal_title, "--", shell, "-c", DEBUG_SCRIPT],
            env=environment,
        )
        deadline = time.monotonic() + 15.0
        pid = read_pid_file(deadline)

        last_error: SessionError | None = None
        while time.monotonic() < deadline:
            try:
                dosbox_window, debugger_window = discover_windows(pid, terminal_title)
                break
            except SessionError as error:
                last_error = error
                time.sleep(0.1)
        else:
            raise SessionError(
                f"session windows were not discovered before timeout: {last_error}"
            )

        state = {
            "session_id": session_id,
            "source": source,
            "source_sha256": sha256_file(PROJECT_DIR / source),
            "terminal_title": terminal_title,
            "dosbox_pid": pid,
            "dosbox_window": dosbox_window,
            "debugger_window": debugger_window,
        }
        write_state(state)
        validate_state(state)
    except Exception:
        STATE_FILE.unlink(missing_ok=True)
        PID_FILE.unlink(missing_ok=True)
        if pid is not None and pid_is_live(pid):
            os.kill(pid, signal.SIGTERM)
        raise
    print("Capture session launched and validated.")
    print(f"session: {session_id}")
    print(f"source: {source}")
    print(f"source SHA-256: {state['source_sha256']}")


def input_action(state: dict[str, object], target: str, action: list[str]) -> None:
    validate_state(state)
    window = int(state[f"{target}_window"])
    result = run_command([sys.executable, str(INPUT_HELPER), f"0x{window:x}", *action])
    print(result.stdout.strip())


def print_status(state: dict[str, object]) -> None:
    validate_state(state)
    print("Capture session is active and both window identities are valid.")
    print(f"session: {state['session_id']}")
    print(f"source: {state['source']}")
    print(f"source SHA-256: {state['source_sha256']}")


def remove_state_files() -> None:
    STATE_FILE.unlink(missing_ok=True)
    PID_FILE.unlink(missing_ok=True)


def close_session(state: dict[str, object]) -> None:
    validate_state(state)
    pid = int(state["dosbox_pid"])
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and pid_is_live(pid):
        time.sleep(0.1)
    if pid_is_live(pid):
        raise SessionError("session did not close after the termination request")
    remove_state_files()
    print("Capture session closed; ignored session state removed.")


def cleanup() -> None:
    state = read_state()
    try:
        validate_state(state)
    except SessionError:
        remove_state_files()
        print("Stale ignored session state removed.")
        return
    raise SessionError("session is still active; use close instead of cleanup")


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.command == "launch":
        launch(arguments.source)
        return 0
    if arguments.command == "cleanup":
        cleanup()
        return 0

    state = read_state()
    if arguments.command == "status":
        print_status(state)
    elif arguments.command == "focus":
        input_action(state, arguments.target, ["focus"])
    elif arguments.command == "open-debugger":
        input_action(state, "dosbox", ["hotkey", "Alt_L", "Pause"])
    elif arguments.command == "type-breakpoint":
        input_action(state, "debugger", ["text", "bpint 3"])
    elif arguments.command == "submit-debugger":
        input_action(state, "debugger", ["key", "Return"])
    elif arguments.command == "resume-debugger":
        input_action(state, "debugger", ["key", "F5"])
    elif arguments.command == "type-breakpoint-list":
        input_action(state, "debugger", ["text", "bplist"])
    elif arguments.command == "type-restore-entry":
        input_action(state, "debugger", ["text", f"sm {arguments.cs}:0000 8c d8"])
    elif arguments.command == "type-delete-breakpoint":
        input_action(state, "debugger", ["text", f"bpdel {arguments.number}"])
    elif arguments.command == "type-data-dump":
        input_action(state, "debugger", ["text", f"memdumpbin {arguments.ds}:0000 2ab0"])
    elif arguments.command == "type-cga-dump":
        input_action(state, "debugger", ["text", "memdumpbin b800:0000 4000"])
    elif arguments.command == "guest-key":
        input_action(state, "dosbox", ["key", arguments.key])
    elif arguments.command == "close":
        close_session(state)
    else:
        raise SessionError(f"unsupported command: {arguments.command}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SessionError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
