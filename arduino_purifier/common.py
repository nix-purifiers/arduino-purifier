import json
import os
import subprocess

SYSTEMS = {"x86_64-linux": "amd64", "aarch64-linux": "arm64"}
NATIVE_ENV = (
    "ARDUINO_DATA_DIR",
    "ARDUINO_DOWNLOADS_DIR",
    "ARDUINO_SKETCHBOOK_DIR",
    "ARDUINO_DIRECTORIES_DATA",
    "ARDUINO_DIRECTORIES_DOWNLOADS",
    "ARDUINO_DIRECTORIES_USER",
    "ARDUINO_BUILD_CACHE_PATH",
    "ARDUINO_PURIFIER_FROZEN",
    "ARDUINO_PURIFIER_REPLAY",
    "ARDUINO_PURIFIER_CAPTURE",
    "ARDUINO_PURIFIER_ARCH",
)


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    return result.stdout


def original_environment():
    env = dict(os.environ)
    for name, value in json.loads(
        env.pop("ARDUINO_PURIFIER_ORIGINAL_ENV", "{}")
    ).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def load(companion):
    data = json.loads(companion.read_text())
    if data.get("sdk") != os.environ["ARDUINO_PURIFIER_SDK_VERSION"]:
        raise ValueError("Arduino SDK changed; run arduino-purifier lock --update")
    if os.environ["ARDUINO_PURIFIER_SYSTEM"] not in data.get("systems", {}):
        raise ValueError("The Arduino lock has no closure for this system")
    return data
