import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from arduino_purifier.common import run
from arduino_purifier.layout import configure

root, state, manifest_file, binary, output = sys.argv[1:]
root, state, output = Path(root), Path(state), Path(output)
manifest = json.loads(Path(manifest_file).read_text())
env = configure(state, packages=manifest["packages"])
selected = json.loads(run([binary, "purifier-project", str(root)], env=env))
if selected != manifest["selection"]:
    raise ValueError(
        "Arduino profile selection changed; run arduino-purifier lock --update"
    )
for profile in selected["profiles"]:
    build = state / "build" / profile["name"]
    subprocess.run(
        [
            binary,
            "compile",
            "--profile",
            profile["name"],
            "--build-path",
            str(build),
            str(root),
        ],
        env=env,
        check=True,
    )
    destination = output / profile["name"]
    destination.mkdir(parents=True, exist_ok=True)
    for suffix in ("hex", "elf"):
        shutil.copyfile(
            build / (root.name + ".ino." + suffix), destination / ("firmware." + suffix)
        )
