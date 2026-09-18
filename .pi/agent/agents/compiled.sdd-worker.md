---
name: compiled.sdd-worker
description: Permission profile for compiled.sdd-worker (native permission key).
permission:
  tools:
    "*": allow
    ls: deny
    find: deny
    grep: deny
  bash:
    "*": allow
    "ls*": deny
    "find*": deny
    "grep*": deny
    "cat*": deny
---

PERMISSION-ONLY profile. No runtime body.
