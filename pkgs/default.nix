{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.arduino-cli;
  core = scope.original.pureGoPkg.overrideAttrs (old: {
    postPatch =
      (old.postPatch or "")
      + "\n${pkgs.python3}/bin/python3 ${../native/patch.py} ${../native/capture.go} ${../native/project.go}\n";
  });
  debugger = pkgs.gdb;
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      arduino = toString scope.original.pureGoPkg.src;
      debugger = toString scope.debugger.src;
      patch = builtins.hashFile "sha256" ../native/patch.py;
      capture = builtins.hashFile "sha256" ../native/capture.go;
      project = builtins.hashFile "sha256" ../native/project.go;
      normalize = builtins.hashFile "sha256" ../native/normalize.py;
    }
  );
  cli = scope.callPackage ./cli/default.nix { inherit nixpkgsSrc purifierSrc; };
  buildArduinoProject = scope.callPackage ./build-arduino-project/default.nix { };
})
