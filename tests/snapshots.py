import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
with tempfile.TemporaryDirectory(prefix="arduino-snapshot-replay-") as temporary:
    root = Path(temporary) / "minimal"
    shutil.copytree(repo / "examples/minimal", root)
    companion = root / "arduino-purifier.lock.json"
    data = json.loads(companion.read_text())
    urls = []
    for index, entry in enumerate(data["systems"][system]["entries"]):
        if "indexSnapshot" in entry:
            urls.append(entry["url"])
            # A unique output name prevents the local Nix store from hiding a fetch.
            entry["path"] = "snapshot-probe-" + uuid.uuid4().hex + "-" + str(index)
    assert len(urls) >= 2
    companion.write_text(json.dumps(data))
    expression = (
        """let
 f=builtins.getFlake """
        + json.dumps(str(repo))
        + """;
 p=import f.inputs.nixpkgs {};
 scope=import """
        + json.dumps(str(repo / "nix/scope.nix"))
        + """ {pkgs=p;nixpkgsSrc=f.inputs.nixpkgs;purifierSrc=f.inputs.purifier;};
 lock=f.lib.arduino-purifier.readLock {src=/. + """
        + json.dumps(str(root))
        + """;};
 guarded=args: if builtins.any (url: builtins.elem url """
        + json.dumps(urls).replace(", ", " ")
        + """) args.urls then throw "Mutable Arduino index fetch attempted" else p.fetchurl args;
 environment=scope.callPackage """
        + json.dumps(str(repo / "nix/environment.nix"))
        + """ {} {inherit lock;fetchers.fetchurl=guarded;};
 in environment.packages"""
    )
    # Nix lists use whitespace; JSON string arrays here need explicit decoding.
    expression = expression.replace(
        json.dumps(urls).replace(", ", " "),
        "(builtins.fromJSON " + json.dumps(json.dumps(urls)) + ")",
    )
    subprocess.run(
        ["nix", "build", "--impure", "--no-link", "--expr", expression], check=True
    )
print(
    "Fresh fixed-output index snapshots replay natively without fetching mutable upstream indexes"
)
