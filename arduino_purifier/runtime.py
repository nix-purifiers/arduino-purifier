import hashlib
import json
import os
from pathlib import Path
import subprocess

from .common import load, original_environment, run
from .layout import configure


def realize(root, companion):
    data = load(companion)
    sdk = os.environ["ARDUINO_PURIFIER_SDK"]
    home = Path(
        original_environment().get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    )
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    generation = hashlib.sha256(companion.read_bytes() + sdk.encode()).hexdigest()[:20]
    state = home / "arduino-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    profile = state / "environment-profile"
    if not profile.exists():
        expression = (
            "import "
            + json.dumps(sdk + "/lib/arduino-purifier/pkgs/build-arduino-project/realize.nix")
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";sdk="
            + json.dumps(sdk)
            + ";}"
        )
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(profile),
            ]
        )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Arduino SDK differs from the lock")
    return state, data, manifest


def execute(
    root, companion, args, environment=None, verify_only=False, native_directory=None
):
    state, data, manifest = realize(root, companion)
    env = configure(
        state / "session", packages=manifest["packages"], environment=environment
    )
    binary = os.environ["ARDUINO_PURIFIER_CORE"]
    selected = json.loads(run([binary, "purifier-project", str(root)], env=env))
    if selected != manifest["selection"]:
        raise ValueError(
            "Arduino profile selection changed; run arduino-purifier lock --update"
        )
    if verify_only:
        return 0
    env.update(ARDUINO_PURIFIER_PROJECT=str(root), ARDUINO_PURIFIER_LOCK=str(companion))
    return subprocess.call([binary, *args], cwd=native_directory or root, env=env)
