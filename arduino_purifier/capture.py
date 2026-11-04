import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from .common import SYSTEMS, run
from .layout import configure


def capture(root, companion, update=False):
    if companion.exists() and not update:
        from .runtime import execute

        execute(root, companion, [], verify_only=True)
        return
    binary = os.environ["ARDUINO_PURIFIER_CORE"]
    with tempfile.TemporaryDirectory(prefix="arduino-capture-") as temporary:
        state = Path(temporary)
        systems = {}
        selection = None
        for system, arch in SYSTEMS.items():
            observed = state / system / "observed"
            observed.mkdir(parents=True)
            env = configure(state / system, capture=observed, arch=arch)
            selected = json.loads(run([binary, "purifier-project", str(root)], env=env))
            if selection is not None and selection != selected:
                raise ValueError(
                    "Arduino native profile selection differs between systems"
                )
            selection = selected
            for profile in selected["profiles"]:
                run(
                    [
                        binary,
                        "compile",
                        "--show-properties",
                        "--profile",
                        profile["name"],
                        str(root),
                    ],
                    env=env,
                )
            records = {}
            for line in (observed / "records.jsonl").read_text().splitlines():
                entry = json.loads(line)
                if (
                    entry["url"] in records
                    and records[entry["url"]]["sha256"] != entry["sha256"]
                ):
                    raise ValueError(
                        "A registry index changed during native capture; retry"
                    )
                records[entry["url"]] = entry
            entries = []
            for index, url in enumerate(sorted(records)):
                item = records[url]
                parsed = urlsplit(url)
                if (
                    parsed.scheme != "https"
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError(
                        "Public stable HTTPS Arduino downloads are required"
                    )
                run(["nix", "store", "add-file", item["archive"]])
                entry = dict(
                    path="archive-" + str(index),
                    url=url,
                    mirrors=[],
                    hash="sha256-"
                    + base64.b64encode(bytes.fromhex(item["sha256"])).decode(),
                )
                if item.get("index") == "true":
                    snapshot = (
                        root
                        / "arduino-purifier.indexes"
                        / (item["sha256"] + ".snapshot")
                    )
                    payload = Path(item["archive"]).read_bytes()
                    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                        raise ValueError("Captured Arduino index digest changed")
                    snapshot.parent.mkdir(parents=True, exist_ok=True)
                    if snapshot.exists():
                        if snapshot.read_bytes() != payload:
                            raise ValueError("Arduino index snapshot was replaced")
                    else:
                        staged_snapshot = snapshot.with_suffix(".tmp")
                        staged_snapshot.write_bytes(payload)
                        staged_snapshot.replace(snapshot)
                    entry["indexSnapshot"] = str(snapshot.relative_to(root))
                entries.append(entry)
            systems[system] = dict(entries=entries)
        candidate = state / "arduino-purifier.lock.json"
        candidate.write_text(
            json.dumps(
                dict(
                    version=2,
                    purifier="arduino",
                    sdk=os.environ["ARDUINO_PURIFIER_SDK_VERSION"],
                    selection=selection,
                    systems=systems,
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        from .runtime import execute

        execute(root, candidate, [], verify_only=True)
        companion.parent.mkdir(parents=True, exist_ok=True)
        staged = companion.with_name(companion.name + ".tmp")
        staged.write_bytes(candidate.read_bytes())
        staged.replace(companion)
