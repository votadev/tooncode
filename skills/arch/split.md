---
name: split
description: Split large file into modules
---

Split {{input}} into smaller modules:

1. Analyze the file - identify logical groups of functions/classes
2. Plan the split:
   - Group by responsibility (single responsibility principle)
   - Identify shared utilities
   - Map dependencies between groups
3. Create new files with proper names
4. Move code, update all imports
5. Verify nothing is broken (run tests or import check)
6. Show the new structure
