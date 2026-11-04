import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="arduino-cold-") as temporary:
    root = Path(temporary) / "minimal"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "arduino-purifier.lock.json"
    lock.unlink()
    ambient = Path(temporary) / "ambient"
    ambient.mkdir()
    (ambient / "preserve").write_text("existing state")
    env = dict(
        os.environ,
        ARDUINO_DIRECTORIES_DATA=str(ambient),
        ARDUINO_DATA_DIR=str(ambient),
        ARDUINO_SKETCHBOOK_DIR=str(ambient),
        ARDUINO_DOWNLOADS_DIR=str(ambient),
        ARDUINO_DIRECTORIES_USER=str(ambient),
        XDG_CACHE_HOME=str(Path(temporary) / "cache"),
    )

    def capture(*args, success=True):
        result = subprocess.run(
            [sdk / "bin/arduino-purifier", "lock", "--project", root, *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=1200,
        )
        assert (result.returncode == 0) == success, result

    capture()
    data = json.loads(lock.read_text())
    assert set(data["systems"]) == {"x86_64-linux", "aarch64-linux"}
    assert data["selection"]["defaultProfile"] == "uno"
    for selected in data["systems"].values():
        assert len(selected["entries"]) == 14
        assert all(
            entry["url"].startswith("https://") and entry["hash"].startswith("sha256-")
            for entry in selected["entries"]
        )
    before = lock.read_bytes()
    capture()
    assert lock.read_bytes() == before
    source = root / "sketch.yaml"
    source.write_text(
        source.read_text().replace("arduino:avr (1.8.6)", "arduino:samd (1.8.14)")
    )
    capture("--update", success=False)
    assert lock.read_bytes() == before
    assert list(ambient.iterdir()) == [ambient / "preserve"]
print(
    "Cold native Arduino capture, both host closures, stable verification, atomic failure and isolated state passed"
)
