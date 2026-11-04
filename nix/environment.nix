{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdkVersion,
  core,
  debugger,
  autoPatchelfHook,
  stdenv,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  snapshots = builtins.listToAttrs (
    map (entry: {
      name = entry.hash;
      value = entry.snapshotSource;
    }) (builtins.filter (entry: entry ? snapshotSource) checked.entries)
  );
  fetchLocked =
    args:
    if builtins.hasAttr args.hash snapshots then
      runCommand args.name {
        snapshot = snapshots.${args.hash};
        outputHash = args.hash;
        outputHashAlgo = "sha256";
        outputHashMode = "flat";
      } ''cp "$snapshot" "$out"''
    else
      (fetchers.fetchurl or fetchurl) args;
  archives = purifier.tree (
    {
      name = "arduino-archives";
      inherit
        runCommand
        fetchgit
        writeText
        python3
        ;
      fetchurl = fetchLocked;
      entries = checked.entries;
    }
    // builtins.removeAttrs fetchers [ "fetchurl" ]
  );
  replay = writeText "arduino-replay.json" (
    builtins.toJSON (
      builtins.listToAttrs (
        map (e: {
          name = e.url;
          value = "${archives}/${e.path}";
        }) checked.entries
      )
    )
  );
  sketch = writeText "sketch.yaml" lock.data.selection.sketchYaml;
  profileCommands = lib.concatMapStringsSep "\n" (
    profile:
    "${core}/bin/arduino-cli compile --show-properties --profile ${lib.escapeShellArg profile.name} project > \"$TMPDIR/properties\""
  ) lock.data.selection.profiles;
  packages =
    runCommand "arduino-native-profile"
      {
        nativeBuildInputs = [ autoPatchelfHook ];
        buildInputs = [ stdenv.cc.cc.lib ];
      }
      ''
        export HOME="$TMPDIR/home" ARDUINO_DIRECTORIES_DATA="$out" ARDUINO_DIRECTORIES_DOWNLOADS="$TMPDIR/downloads" ARDUINO_DIRECTORIES_USER="$TMPDIR/user" ARDUINO_BUILD_CACHE_PATH="$TMPDIR/cache" ARDUINO_PURIFIER_REPLAY=${replay}
        mkdir -p "$HOME" "$out" project
        cp ${sketch} project/sketch.yaml
        printf 'void setup() {}\nvoid loop() {}\n' > project/project.ino
        ${profileCommands}
        ${python3}/bin/python3 ${../native/normalize.py} "$out"
        rm -f "$out/inventory.yaml"
        rm -rf "$out/tmp"
        for debugger in "$out"/internal/*/bin/avr-gdb; do
         if [ -f "$debugger" ]; then rm "$debugger"; fi
        done
        patchShebangs "$out"
        autoPatchelf "$out"
        for compiler in "$out"/internal/*/bin/avr-gcc; do
         if [ -f "$compiler" ]; then ln -s ${lib.getExe debugger} "$(dirname "$compiler")/avr-gdb"; fi
        done
      '';
  output =
    (writeText "arduino-environment.json" (
      builtins.toJSON {
        inherit packages;
        inherit (lock.data) sdk selection;
        providers.avrDebugger = {
          package = "nixpkgs.gdb";
          version = debugger.version;
        };
      }
    )).overrideAttrs
      (_: {
        passthru = { inherit packages; };
      });
in
assert lib.assertMsg (
  lock.data.sdk == sdkVersion
) "Arduino SDK changed; run arduino-purifier lock --update";
{
  inherit output packages;
}
