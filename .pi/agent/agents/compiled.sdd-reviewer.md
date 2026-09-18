---
name: compiled.sdd-reviewer
description: Permission profile for compiled.sdd-reviewer (native permission key).
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
    "rm*": deny
    "* rm *": deny
    "* rm": deny
---

PERMISSION-ONLY profile. No runtime body.
