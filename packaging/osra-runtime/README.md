# macOS OSRA Runtime Placeholder

The local macOS release package can include a bundled OSRA runtime in this directory.

The runtime itself is not committed to Git because it contains large third-party binaries. Release artifacts such as the `.dmg` should be uploaded through GitHub Releases instead of normal git commits.

Expected layout:

```text
osra-runtime/
  bin/osra
  bin/...
  lib/...
  share/chain.txt
  share/superatom.txt
  share/spelling.txt
```
