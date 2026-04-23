---
name: lathe-certification-fix
description: Use when a Lathe asset builds but fails validation or certification, and the goal is to pass the current contract without papering over the defect.
---

Work from the validation evidence back to the smallest real fix.

Workflow:
1. Read the build report and validation diagnostics.
2. Determine whether the failing evidence points to:
   - source intent or build settings
   - a checker rule bug
   - a backend output defect
   - a packaging mismatch
3. Prefer stage-local fixes that preserve the declared contract.
4. Rebuild the asset after the fix and confirm the score and threshold relationship.
5. Add a regression test if the fix affects reusable logic.

Guardrails:
- Do not weaken thresholds or remove `ensure` rules unless the task explicitly changes the contract.
- Keep the certification explanation concrete: name the violated rule, the fix, and the new outcome.
