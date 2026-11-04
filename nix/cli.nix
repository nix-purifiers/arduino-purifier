{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  cacert,
  gnutar,
  gzip,
  unzip,
  coreutils,
  stdenv,
  original,
  core,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "arduino-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/arduino-purifier"
    cp -r arduino_purifier nix native "$out/lib/arduino-purifier/"
    install -m755 bin/arduino-purifier "$out/bin/arduino-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/arduino-purifier/nix/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/arduino-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          gnutar
          gzip
          unzip
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default ARDUINO_PURIFIER_GH ${gh}/bin/gh \
      --set ARDUINO_PURIFIER_ORIGINAL ${original}/bin/arduino-cli \
      --set ARDUINO_PURIFIER_CORE ${core}/bin/arduino-cli \
      --set ARDUINO_PURIFIER_SYSTEM ${stdenv.hostPlatform.system} \
      --set ARDUINO_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set ARDUINO_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/arduino-purifier" "$out/bin/arduino-cli" --add-flags '--native'
  '';
  meta = {
    description = "Arduino with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "arduino-purifier";
  };
}
