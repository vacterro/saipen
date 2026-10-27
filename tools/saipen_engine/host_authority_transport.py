"""Local authenticated-adjacent IPC for the SAIPEN host-authority broker.

This module moves bytes. It authenticates nothing, decides nothing and stores
nothing: a Windows named pipe is bound on Windows and a Unix domain socket on
POSIX, one JSON request frame in and one JSON response frame out per connection.
Every trust decision belongs to the broker that passes the handler in, which
reads the peer's OS identity (`Peer.pid`) itself and refuses a caller it cannot
place. Keeping the transport this empty is the point: if a caller could prove
itself by anything it SENDS, the same-user client this boundary exists to refuse
would be able to send it too.

Framing is one 4-byte big-endian length prefix followed by that many bytes of
UTF-8 JSON, in both directions, on both platforms. A frame larger than
`MAX_FRAME` or of zero length is refused rather than allocated.

`serve` is called with a `threading.Event`; it answers connections until the
event is set and then returns within about a second, because a lifecycle owner
has to be able to shut a broker down without killing it.

The endpoint never disappears while a service is alive. A Windows server that
closed its only pipe instance before creating the next one left a window in
which a second host window was told "no such endpoint", concluded the service
was gone and tried to start another. The next instance is therefore created
BEFORE the answered one is closed, a client that finds every instance busy
waits for one instead of giving up, and the first instance is created
exclusively, so a name that something else already serves is a bind failure
here rather than a second server nobody asked for.

`request` can also be told who the SERVER must be: the client asks the
operating system for the pid on the other end and hands it to the caller's
`verify_server`. A name is only a name, and a process that merely got to it
first is not the service.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import socket
import struct
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import contextlib

__all__ = [
    "MAX_FRAME",
    "Peer",
    "TransportError",
    "available",
    "endpoint",
    "peer_supported",
    "request",
    "serve",
]

MAX_FRAME = 1024 * 1024

_HEADER = struct.Struct(">I")
_POLL_SECONDS = 0.01
_ACCEPT_POLL_SECONDS = 0.05
_FRAME_TIMEOUT_SECONDS = 5.0
_ACCEPT_TIMEOUT_SECONDS = 0.25
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:  # pragma: no cover - platform branch, exercised on Windows only
    from ctypes import wintypes

    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _OPEN_EXISTING = 3
    _PIPE_ACCESS_DUPLEX = 0x00000003
    _PIPE_TYPE_BYTE = 0x00000000
    _PIPE_READMODE_BYTE = 0x00000000
    _PIPE_WAIT = 0x00000000
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _ERROR_FILE_NOT_FOUND = 2
    _ERROR_ACCESS_DENIED = 5
    _ERROR_PIPE_BUSY = 231
    _FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
    _PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
    _ERROR_PIPE_CONNECTED = 535
    _BUFFER_BYTES = 65536
    _MAX_INSTANCES = 255

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _KERNEL32.CreateNamedPipeW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
    )
    _KERNEL32.CreateNamedPipeW.restype = wintypes.HANDLE
    _KERNEL32.ConnectNamedPipe.argtypes = (wintypes.HANDLE, wintypes.LPVOID)
    _KERNEL32.ConnectNamedPipe.restype = wintypes.BOOL
    _KERNEL32.DisconnectNamedPipe.argtypes = (wintypes.HANDLE,)
    _KERNEL32.DisconnectNamedPipe.restype = wintypes.BOOL
    _KERNEL32.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
    _KERNEL32.FlushFileBuffers.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = (wintypes.HANDLE,)
    _KERNEL32.CloseHandle.restype = wintypes.BOOL
    _KERNEL32.ReadFile.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPVOID,
    )
    _KERNEL32.ReadFile.restype = wintypes.BOOL
    _KERNEL32.WriteFile.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPVOID,
    )
    _KERNEL32.WriteFile.restype = wintypes.BOOL
    _KERNEL32.PeekNamedPipe.argtypes = (
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
        wintypes.LPDWORD,
    )
    _KERNEL32.PeekNamedPipe.restype = wintypes.BOOL
    _KERNEL32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    _KERNEL32.CreateFileW.restype = wintypes.HANDLE

    _KERNEL32.WaitNamedPipeW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    _KERNEL32.WaitNamedPipeW.restype = wintypes.BOOL

    _GET_PIPE_PID = getattr(_KERNEL32, "GetNamedPipeClientProcessId", None)
    if _GET_PIPE_PID is not None:
        _GET_PIPE_PID.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG))
        _GET_PIPE_PID.restype = wintypes.BOOL
    _GET_SERVER_PID = getattr(_KERNEL32, "GetNamedPipeServerProcessId", None)
    if _GET_SERVER_PID is not None:
        _GET_SERVER_PID.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG))
        _GET_SERVER_PID.restype = wintypes.BOOL


class TransportError(RuntimeError):
    """A connect or framing failure, classified by `.kind` for the caller."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class Peer:
    """Who is on the other end, as far as the operating system will say."""

    kind: str
    pid: int | None


def endpoint(scope: str) -> str:
    """The endpoint name for a pre-sanitized scope token.

    The caller owns the token; it is never re-derived or escaped here, so two
    callers that pass the same token always meet on the same endpoint.
    """
    if IS_WINDOWS:
        return "\\\\.\\pipe\\saipen-authority-" + scope
    return str(Path(tempfile.gettempdir()) / ("saipen-authority-" + scope + ".sock"))


def available() -> bool:
    """True when this platform can both bind and connect a local endpoint."""
    if IS_WINDOWS:
        return True
    return hasattr(socket, "AF_UNIX")


def peer_supported() -> bool:
    """True when the platform genuinely supplies an OS-derived client pid."""
    if IS_WINDOWS:
        return _GET_PIPE_PID is not None
    return hasattr(socket, "SO_PEERCRED")


# --------------------------------------------------------------- framing


def _frame_size(header: bytes) -> int:
    size = _HEADER.unpack(header)[0]
    if size == 0 or size > MAX_FRAME:
        raise TransportError("frame", f"declared length {size}")
    return size


def _pack(payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if not body or len(body) > MAX_FRAME:
        raise TransportError("frame", f"response size {len(body)}")
    return _HEADER.pack(len(body)) + body


def _unpack(body: bytes) -> dict:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TransportError("frame", f"unreadable JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TransportError("frame", "frame is not a JSON object")
    return payload


def _dispatch(handler: Callable[[dict, Peer], dict], payload: dict, peer: Peer) -> dict:
    """The handler never raises out of here; a fault becomes a refusal."""
    if not isinstance(payload, dict):
        return {"ok": False, "code": "BAD_REQUEST"}
    try:
        result = handler(payload, peer)
    except Exception:  # a handler fault must not end the service loop
        return {"ok": False, "code": "HANDLER_ERROR"}
    if not isinstance(result, dict):
        return {"ok": False, "code": "HANDLER_ERROR"}
    return result


if IS_WINDOWS:  # pragma: no cover - platform branch, exercised on Windows only

    def _win_create(name: str, first: bool = False):
        """One pipe instance. `first` claims the name exclusively: if anything
        already serves it, this fails instead of joining a foreign server."""
        return _KERNEL32.CreateNamedPipeW(
            name,
            _PIPE_ACCESS_DUPLEX | (_FILE_FLAG_FIRST_PIPE_INSTANCE if first else 0),
            _PIPE_TYPE_BYTE | _PIPE_READMODE_BYTE | _PIPE_WAIT | _PIPE_REJECT_REMOTE_CLIENTS,
            _MAX_INSTANCES,
            _BUFFER_BYTES,
            _BUFFER_BYTES,
            0,
            None,
        )

    def _win_connect(handle) -> bool:
        if _KERNEL32.ConnectNamedPipe(handle, None):
            return True
        return ctypes.get_last_error() == _ERROR_PIPE_CONNECTED

    def _win_close(handle) -> None:
        with contextlib.suppress(OSError):
            _KERNEL32.CloseHandle(handle)

    def _win_peer(handle) -> Peer:
        if _GET_PIPE_PID is None:
            return Peer("named-pipe", None)
        pid = wintypes.ULONG(0)
        if _GET_PIPE_PID(handle, ctypes.byref(pid)):
            return Peer("named-pipe", int(pid.value))
        return Peer("named-pipe", None)

    def _win_read(handle, count: int, deadline: float) -> bytes:
        buffer = ctypes.create_string_buffer(count)
        got = 0
        while got < count:
            if time.monotonic() > deadline:
                raise TransportError("timeout", "peer did not finish its frame")
            available_bytes = wintypes.DWORD(0)
            if not _KERNEL32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(available_bytes), None
            ):
                raise TransportError("io", "peer closed the pipe")
            if available_bytes.value == 0:
                time.sleep(_POLL_SECONDS)
                continue
            chunk = min(count - got, available_bytes.value)
            read = wintypes.DWORD(0)
            if not _KERNEL32.ReadFile(
                handle, ctypes.byref(buffer, got), chunk, ctypes.byref(read), None
            ):
                raise TransportError("io", "read failed")
            got += read.value
        return buffer.raw[:count]

    def _win_write(handle, blob: bytes) -> bool:
        written = wintypes.DWORD(0)
        body = ctypes.create_string_buffer(blob, len(blob))
        if not _KERNEL32.WriteFile(handle, body, len(blob), ctypes.byref(written), None):
            return False
        return written.value == len(blob)

    def _win_release(name: str) -> None:
        """One self-connect, so a blocked ConnectNamedPipe can be abandoned."""
        handle = _KERNEL32.CreateFileW(
            name, _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING, 0, None
        )
        if handle != _INVALID_HANDLE_VALUE:
            _win_close(handle)

    def _win_answer(handle, handler) -> bool:
        """Read one frame from a connected instance, answer it, hang up."""
        try:
            peer = _win_peer(handle)
            deadline = time.monotonic() + _FRAME_TIMEOUT_SECONDS
            response = None
            payload: dict = {}
            try:
                size = _frame_size(_win_read(handle, _HEADER.size, deadline))
                payload = _unpack(_win_read(handle, size, deadline))
            except TransportError:
                response = {"ok": False, "code": "BAD_REQUEST"}
            if response is None:
                response = _dispatch(handler, payload, peer)
            try:
                if _win_write(handle, _pack(response)):
                    _KERNEL32.FlushFileBuffers(handle)
                    return True
            except TransportError:
                pass
            return False
        finally:
            _KERNEL32.DisconnectNamedPipe(handle)
            _win_close(handle)

    def _win_serve(name: str, handler, stop, max_requests: int | None) -> None:
        served = 0
        listening = _win_create(name, first=True)
        if listening == _INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error == _ERROR_ACCESS_DENIED:
                raise TransportError("bind", "the endpoint is already served by another process")
            raise TransportError("bind", f"CreateNamedPipeW failed ({error})")
        try:
            while not stop.is_set() and (max_requests is None or served < max_requests):
                accepted = {"ok": False}
                connected = threading.Event()

                def accept(handle=listening, accepted=accepted, connected=connected) -> None:
                    accepted["ok"] = _win_connect(handle)
                    connected.set()

                threading.Thread(target=accept, daemon=True).start()
                while not connected.wait(_ACCEPT_POLL_SECONDS):
                    if stop.is_set():
                        _win_release(name)
                        connected.wait(1.0)
                        return
                if not accepted["ok"] or stop.is_set():
                    return
                current = listening
                # The next instance exists before this one is answered and
                # closed, so the name never vanishes while the service lives.
                listening = _win_create(name)
                if listening == _INVALID_HANDLE_VALUE:
                    _win_answer(current, handler)
                    raise TransportError(
                        "bind", f"CreateNamedPipeW failed ({ctypes.get_last_error()})"
                    )
                if _win_answer(current, handler):
                    served += 1
        finally:
            if listening != _INVALID_HANDLE_VALUE:
                _win_close(listening)

    def _win_server_pid(handle) -> int | None:
        if _GET_SERVER_PID is None:
            return None
        pid = wintypes.ULONG(0)
        if _GET_SERVER_PID(handle, ctypes.byref(pid)):
            return int(pid.value)
        return None

    def _win_request(name: str, payload: dict, timeout: float, verify_server=None) -> dict:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            handle = _KERNEL32.CreateFileW(
                name, _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING, 0, None
            )
            if handle != _INVALID_HANDLE_VALUE:
                break
            error = ctypes.get_last_error()
            if error == _ERROR_PIPE_BUSY:
                # Every instance is answering someone else: the service is
                # there. Wait for an instance instead of calling it absent.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TransportError("timeout", "the endpoint stayed busy")
                _KERNEL32.WaitNamedPipeW(name, max(1, int(min(remaining, 2.0) * 1000)))
                continue
            if error == _ERROR_FILE_NOT_FOUND:
                raise TransportError("absent", f"no endpoint ({error})")
            raise TransportError("absent", f"CreateFileW failed ({error})")
        try:
            if verify_server is not None and not verify_server(_win_server_pid(handle)):
                raise TransportError("impostor", "the endpoint is not served by the service")
            if not _win_write(handle, _pack(payload)):
                raise TransportError("io", "request was not written")
            _KERNEL32.FlushFileBuffers(handle)
            size = _frame_size(_win_read(handle, _HEADER.size, deadline))
            return _unpack(_win_read(handle, size, deadline))
        finally:
            _win_close(handle)


# --------------------------------------------------------------- POSIX


def _posix_peer(connection: socket.socket) -> Peer:
    if not hasattr(socket, "SO_PEERCRED"):
        return Peer("unix-socket", None)
    try:
        raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return Peer("unix-socket", int(struct.unpack("3i", raw)[0]))
    except OSError:
        return Peer("unix-socket", None)


def _recv_exact(connection: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        try:
            chunk = connection.recv(count - len(chunks))
        except socket.timeout as exc:
            raise TransportError("timeout", "peer did not finish its frame") from exc
        except OSError as exc:
            raise TransportError("io", "peer closed the endpoint") from exc
        if not chunk:
            raise TransportError("io", "peer closed the endpoint")
        chunks.extend(chunk)
    return bytes(chunks)


def _safe_send(connection: socket.socket, payload: dict) -> bool:
    try:
        connection.sendall(_pack(payload))
        return True
    except (OSError, TransportError):
        return False


def _posix_connection(connection: socket.socket, handler, peer: Peer) -> bool:
    try:
        connection.settimeout(_FRAME_TIMEOUT_SECONDS)
        size = _frame_size(_recv_exact(connection, _HEADER.size))
        payload = _unpack(_recv_exact(connection, size))
    except TransportError:
        return _safe_send(connection, {"ok": False, "code": "BAD_REQUEST"})
    return _safe_send(connection, _dispatch(handler, payload, peer))


def _posix_serve(name: str, handler, stop, max_requests: int | None) -> None:
    path = name
    try:
        os.unlink(path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise TransportError("bind", f"stale endpoint not removable: {exc}") from exc
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    served = 0
    try:
        try:
            server.bind(path)
        except OSError as exc:
            raise TransportError("bind", str(exc)) from exc
        os.chmod(path, 0o600)
        server.listen(64)
        server.settimeout(_ACCEPT_TIMEOUT_SECONDS)
        while not stop.is_set() and (max_requests is None or served < max_requests):
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if stop.is_set():
                    break
                continue
            try:
                if _posix_connection(connection, handler, _posix_peer(connection)):
                    served += 1
            finally:
                connection.close()
    finally:
        server.close()
        with contextlib.suppress(OSError):
            os.unlink(path)


def _posix_request(name: str, payload: dict, timeout: float, verify_server=None) -> dict:
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        try:
            connection.connect(name)
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise TransportError("absent", str(exc)) from exc
        except socket.timeout as exc:
            raise TransportError("timeout", "connect timed out") from exc
        except OSError as exc:
            raise TransportError("absent", str(exc)) from exc
        if verify_server is not None and not verify_server(_posix_peer(connection).pid):
            raise TransportError("impostor", "the endpoint is not served by the service")
        try:
            connection.sendall(_pack(payload))
        except (OSError, TransportError) as exc:
            raise TransportError("io", str(exc)) from exc
        size = _frame_size(_recv_exact(connection, _HEADER.size))
        return _unpack(_recv_exact(connection, size))
    finally:
        connection.close()


# --------------------------------------------------------------- surface


def serve(
    name: str,
    handler: Callable[[dict, Peer], dict],
    *,
    stop: threading.Event,
    max_requests: int | None = None,
) -> None:
    """Answer request frames on `name` until `stop` is set.

    One connection carries exactly one request and exactly one response; a
    malformed frame is answered with `BAD_REQUEST` and the loop continues, so no
    client can take the service down by misbehaving.
    """
    if not available():
        raise TransportError("unsupported", "this platform cannot serve a local endpoint")
    if IS_WINDOWS:
        _win_serve(name, handler, stop, max_requests)
    else:
        _posix_serve(name, handler, stop, max_requests)


def request(name: str, payload: dict, *, timeout: float = 5.0, verify_server=None) -> dict:
    """Send one request frame to `name` and return the one response frame.

    `verify_server`, when given, is called with the OS-reported pid of the
    process serving the endpoint (None where the platform will not say) BEFORE
    anything is sent; a False answer raises `TransportError("impostor")`.
    """
    if not available():
        raise TransportError("unsupported", "this platform cannot connect a local endpoint")
    if IS_WINDOWS:
        return _win_request(name, payload, timeout, verify_server)
    return _posix_request(name, payload, timeout, verify_server)
