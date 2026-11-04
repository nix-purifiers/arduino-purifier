import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)

with tempfile.TemporaryDirectory(prefix="arduino proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "minimal"
    shutil.copytree(repo / "examples/minimal", root)
    poisoned = temp / "ambient-data/preserve"
    poisoned.parent.mkdir(parents=True)
    poisoned.write_text("ambient Arduino data\n")
    ambient = temp / "ambient-core/preserve"
    ambient.parent.mkdir()
    ambient.write_text("existing global state\n")
    env = dict(
        os.environ,
        ARDUINO_PURIFIER_PROJECT=str(root),
        ARDUINO_DIRECTORIES_DATA=str(poisoned.parent),
        ARDUINO_DATA_DIR=str(poisoned.parent),
        ARDUINO_SKETCHBOOK_DIR=str(ambient.parent),
        ARDUINO_DOWNLOADS_DIR=str(ambient.parent),
        ARDUINO_DIRECTORIES_USER=str(ambient.parent),
        XDG_CACHE_HOME=str(temp / "cache"),
    )

    def call(name, *args, success=True, extra=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=root,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    companion = root / "arduino-purifier.lock.json"
    before = companion.read_bytes()
    source = root / "minimal.ino"
    original = source.read_text()
    hashes = []
    for answer in [42, 43, 42]:
        source.write_text(original.replace("= 42;", "= " + str(answer) + ";"))
        shutil.rmtree(temp / "build", ignore_errors=True)
        call("arduino-cli", "compile", "--build-path", str(temp / "build"))
        hashes.append(
            hashlib.sha256((temp / "build/minimal.ino.hex").read_bytes()).hexdigest()
        )
    assert hashes[0] == hashes[2] and hashes[0] != hashes[1], hashes
    assert companion.read_bytes() == before
    assert poisoned.read_text() == "ambient Arduino data\n"
    assert ambient.read_text() == "existing global state\n"
    profiles = list((temp / "cache/arduino-purifier").glob("*/*/environment-profile"))
    assert len(profiles) == 1
    profile = profiles[0]
    assert str(sdk) in subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    packages = Path(manifest["packages"])
    assert not packages.stat().st_mode & 0o222
    assert manifest["providers"]["avrDebugger"]["package"] == "nixpkgs.gdb"
    persistent = profile.parent / "session/cache/preserve"
    persistent.parent.mkdir(parents=True, exist_ok=True)
    persistent.write_text("private state")
    call("arduino-cli", "compile", "--build-path", str(temp / "build"))
    assert persistent.read_text() == "private state"
    config = root / "sketch.yaml"
    configuration = config.read_text()
    config.write_text(configuration + "default_port: /dev/purifier-fixture\n")
    call(
        "arduino-cli",
        "compile",
        "--build-path",
        str(temp / "build"),
        "--build-property",
        "compiler.cpp.extra_flags=-DPURIFIER_BODY_EDIT=43",
    )
    config.write_text(
        configuration.replace("ArduinoJson (7.4.3)", "ArduinoJson (7.3.0)")
    )
    assert "selection changed" in call("arduino-cli", "compile", success=False).stderr
    config.write_text(configuration)
    denied = call(
        "arduino-cli",
        "lib",
        "install",
        "--git-url",
        "https://github.com/purifier/missing.git",
        success=False,
        extra={"ARDUINO_LIBRARY_ENABLE_UNSAFE_INSTALL": "true"},
    )
    assert "Nix-resolved" in denied.stderr + denied.stdout, denied
    denied = call("arduino-cli", "core", "install", "arduino:avr@1.8.6", success=False)
    assert "Nix-resolved" in denied.stderr + denied.stdout, denied

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        command = (
            "from urllib.request import urlopen;print(urlopen("
            + repr("http://127.0.0.1:" + str(server.server_port) + "/")
            + ").read().decode())"
        )
        assert (
            call(
                "arduino-purifier", "exec", "--", "python3", "-c", command
            ).stdout.strip()
            == "42"
        )
    finally:
        server.shutdown()
        server.server_close()
    external = temp / "external-lock.json"
    companion.rename(external)
    flags = {"ARDUINO_PURIFIER_LOCK": str(external)}
    call("arduino-cli", "compile", "--build-path", str(temp / "build"), extra=flags)
    archive = Path(call("arduino-purifier", "bundle", extra=flags).stdout.strip())
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as released:
        released.extractall(consumer, filter="data")
    # Native GNU utilities consume the firmware artifact without this adapter.
    toolchain = next((packages / "internal").glob("*/bin/avr-objcopy")).parent
    subprocess.run(
        [
            toolchain / "avr-objcopy",
            "-I",
            "ihex",
            "-O",
            "binary",
            consumer / "uno/firmware.hex",
            consumer / "firmware.bin",
        ],
        check=True,
    )
    assert (consumer / "firmware.bin").stat().st_size > 0
    result = subprocess.run(
        [
            toolchain / "avr-gdb",
            "--batch",
            "-nx",
            "-ex",
            'file "' + str(consumer / "uno/firmware.elf") + '"',
            "-ex",
            "info target",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0 and "avr" in result.stdout.lower(), result
    fake = temp / "fake-gh"
    publication = temp / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath("
        + repr(str(publication))
        + ").write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake.chmod(0o755)
    call(
        "arduino-purifier",
        "publish",
        "--tag",
        "v-proof",
        extra=dict(flags, ARDUINO_PURIFIER_GH=str(fake)),
    )
    assert json.loads(publication.read_text()) == [
        "release",
        "upload",
        "v-proof",
        str(archive),
        "--clobber",
    ]
    fallback = temp / "fallback"
    fallback.mkdir()
    raw = Path(
        call(
            "arduino-purifier",
            "exec",
            "--",
            "sh",
            "-c",
            'printf "%s" "$ARDUINO_PURIFIER_ORIGINAL"',
            extra=flags,
        ).stdout
    )
    ordinary = subprocess.run(
        [raw, "version"], cwd=fallback, env=env, text=True, capture_output=True
    )
    result = subprocess.run(
        [sdk / "bin/arduino-cli", "version"],
        cwd=fallback,
        env=dict(env, ARDUINO_PURIFIER_PROJECT=str(fallback)),
        text=True,
        capture_output=True,
    )
    assert "ordinary impure" in result.stderr
    assert (
        result.returncode == ordinary.returncode and result.stdout == ordinary.stdout
    ), (result, ordinary)
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/arduino-purifier"),
        ARDUINO_PURIFIER_ORIGINAL=str(fake),
        ARDUINO_PURIFIER_PROJECT=str(fallback),
    )
    result = subprocess.run(
        ["python3", "-m", "arduino_purifier.cli", "--native"],
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result

print(
    "Native Arduino firmware42/43/42, profile and mutation guards, immutable packages, networking, firmware consumer, publication and fallback passed"
)
