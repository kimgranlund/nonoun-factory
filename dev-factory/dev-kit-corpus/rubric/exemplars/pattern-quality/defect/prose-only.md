---
name: prose-only
description: >
  Planted defect — a pattern written as prose with NO structured (```json) block. It cannot be mechanically
  gated for provenance or falsifiability; the gate must REJECT it on schema-valid.
---
# prose only

When a worker keeps failing the same cell, you should probably stop retrying it and mark it blocked so the
loop moves on to other work. This usually happens after a couple of attempts. It's a good idea to record why
it was blocked so a human can look later. Generally this keeps the frontier healthy and avoids burning the
budget on a stuck cell — but none of this is written as a retrievable, provenance-bearing pattern.
