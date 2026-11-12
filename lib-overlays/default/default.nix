final: prev: {
  arduino-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
