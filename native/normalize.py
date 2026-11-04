import json
from pathlib import Path
import sys

for path in Path(sys.argv[1]).glob("internal/*/installed.json"):
    data = json.loads(path.read_text())
    # Native IndexFromPlatformRelease emits tool definitions from Go maps.
    # Definition order has no meaning; retain all native fields and flavor order.
    for package in data["packages"]:
        package["tools"].sort(key=lambda tool: (tool["name"], tool["version"]))
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
