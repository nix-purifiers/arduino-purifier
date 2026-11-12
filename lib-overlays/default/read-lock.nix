{ lib }:
{
  src,
  lockFile ? src + "/arduino-purifier.lock.json",
  system ? builtins.currentSystem,
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  systems = data.systems or { };
  selected = if builtins.isAttrs systems then systems.${system} or { } else { };
  entries = selected.entries or [ ];
  safe =
    s:
    builtins.isString s
    && builtins.match "[A-Za-z0-9_.+-]+" s != null
    && !(builtins.elem s [
      "."
      ".."
    ]);
  shape =
    (data.version or null) == 2
    && (data.purifier or null) == "arduino"
    && builtins.isString (data.sdk or null)
    && builtins.isAttrs (data.selection or null)
    && builtins.isString (data.selection.sketchYaml or null)
    && builtins.isList (data.selection.profiles or null)
    && data.selection.profiles != [ ]
    && builtins.all (
      p: builtins.isAttrs p && safe (p.name or null) && builtins.isString (p.fqbn or null)
    ) data.selection.profiles
    && builtins.isAttrs selected
    && builtins.isList entries
    && entries != [ ]
    && builtins.all (
      e:
      builtins.isAttrs e
      && safe (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isList (e.mirrors or null)
      && builtins.all builtins.isString e.mirrors
      && (
        !(e ? indexSnapshot)
        || (
          builtins.isString e.indexSnapshot
          && builtins.match "arduino-purifier[.]indexes/[0-9a-f]{64}[.]snapshot" e.indexSnapshot != null
          && builtins.pathExists (src + ("/" + e.indexSnapshot))
          &&
            e.indexSnapshot == "arduino-purifier.indexes/"
            + builtins.hashFile "sha256" (src + ("/" + e.indexSnapshot))
            + ".snapshot"
        )
      )
    ) entries;
  valid =
    shape
    && builtins.hasAttr system systems
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.length (lib.unique (map (e: e.url) entries)) == builtins.length entries
    &&
      builtins.length (lib.unique (map (p: p.name) data.selection.profiles))
      == builtins.length data.selection.profiles;
in
{
  purifier = "arduino";
  inherit data selected;
  entries = map (
    entry:
    entry
    // lib.optionalAttrs (entry ? indexSnapshot) { snapshotSource = src + ("/" + entry.indexSnapshot); }
  ) entries;
  problems =
    lib.optional (!valid)
      "Arduino lock or committed index snapshots are missing or malformed; restore them or run arduino-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
