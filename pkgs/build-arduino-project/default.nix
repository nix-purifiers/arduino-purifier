{
  lib,
  runCommand,
  writeText,
  python3,
  fetchurl,
  fetchgit,
  purifier,
  sdkVersion,
  core,
  debugger,
  autoPatchelfHook,
  stdenv,
  gnutar,
  gzip,
  ...
}@scope:
{
  src,
  lockFile ? src + "/arduino-purifier.lock.json",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      inherit src lockFile;
      system = stdenv.hostPlatform.system;
    }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        "result"
        "__pycache__"
      ]);
  };
  name = baseNameOf (toString src);
  driver = lib.fileset.toSource {
    root = ../..;
    fileset = lib.fileset.unions [
      ../../arduino_purifier/common.py
      ../../arduino_purifier/layout.py
      ../../native/check.py
    ];
  };
  project = runCommand "arduino-native-firmware" { } ''
    mkdir -p workspace
    project_name=${lib.escapeShellArg name}
    cp -r ${source} "workspace/$project_name"
    chmod -R u+w workspace
    ${python3}/bin/python3 ${driver}/native/check.py "$PWD/workspace/$project_name" "$TMPDIR/private" ${prepared.output} ${core}/bin/arduino-cli "$out"
    ${lib.optionalString doCheck checkCommand}
  '';
  release =
    runCommand "arduino-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/firmware.tar.gz" -C ${project} .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
