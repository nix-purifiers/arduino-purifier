import json
from pathlib import Path
from .common import NATIVE_ENV, original_environment


def configure(state, packages=None, capture=None, arch=None, environment=None):
    env = original_environment() if environment is None else dict(environment)
    env["ARDUINO_PURIFIER_ORIGINAL_ENV"] = json.dumps(
        {name: env.get(name) for name in NATIVE_ENV}
    )
    for name in ("ARDUINO_DATA_DIR", "ARDUINO_DOWNLOADS_DIR", "ARDUINO_SKETCHBOOK_DIR"):
        env.pop(name, None)
    state = Path(state)
    data = state / "data"
    data.mkdir(parents=True, exist_ok=True)
    if packages is not None:
        for item in Path(packages).iterdir():
            alias = data / item.name
            if alias.is_symlink():
                if alias.resolve() != item.resolve():
                    raise ValueError("Private Arduino dependency alias changed")
            elif alias.exists():
                raise ValueError("Private Arduino dependency alias was replaced")
            else:
                alias.symlink_to(item, target_is_directory=item.is_dir())
    env.update(
        ARDUINO_DIRECTORIES_DATA=str(data),
        ARDUINO_DIRECTORIES_DOWNLOADS=str(state / "downloads"),
        ARDUINO_DIRECTORIES_USER=str(state / "user"),
        ARDUINO_BUILD_CACHE_PATH=str(state / "cache"),
    )
    for name in (
        "ARDUINO_PURIFIER_FROZEN",
        "ARDUINO_PURIFIER_REPLAY",
        "ARDUINO_PURIFIER_CAPTURE",
        "ARDUINO_PURIFIER_ARCH",
    ):
        env.pop(name, None)
    if capture is not None:
        env.update(ARDUINO_PURIFIER_CAPTURE=str(capture), ARDUINO_PURIFIER_ARCH=arch)
    else:
        env["ARDUINO_PURIFIER_FROZEN"] = "1"
    return env
