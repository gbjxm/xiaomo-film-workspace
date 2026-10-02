# Errors

Command failures and integration errors.

---

## [ERR-20260904-001] cinematic_palette_output_branch

**Logged**: 2026-09-04T21:26:29+08:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
Selected the unlabeled SCENE SWATCH BRIDGE format when the user expected a standard professional palette sheet with a title, functional labels, and HEX codes.

### Error
```text
The delivered prompt explicitly requested no title, labels, numbers, or HEX text, so the generated palette contained only unlabeled color blocks.
```

### Context
- The user requested a bedroom scene color-card prompt and expected the previously used labeled production-card format.
- The selected bridge branch intentionally suppresses labels and HEX values; the missing information was caused by prompt construction, not by the image generator.
- The output was not written into the formal C project palette index and was not adopted as a project color card.

### Suggested Fix
Before choosing SCENE SWATCH BRIDGE, check whether the user expects pure visual swatches or a standard labeled production palette. If labels or color codes are expected, use the standard palette output with an exact title, English functional labels, uppercase sRGB HEX values, and matching order; use the unlabeled bridge only when pure swatches are explicitly wanted.

### Metadata
- Reproducible: yes
- Related Files: D:/ProgramData/CodexHome/skills/cinematic-palette-architect/SKILL.md; D:/ProgramData/CodexHome/skills/cinematic-palette-architect/references/output-contract.md

### Resolution
- **Resolved**: 2026-09-04T21:26:29+08:00
- **Notes**: Replaced the unlabeled specification with a nine-color labeled palette prompt using sampled center colors from the returned swatch image.

---

## [ERR-20260903-001] record_improvement.ps1

**Logged**: 2026-09-03T09:27:15+08:00
**Priority**: low
**Status**: pending
**Area**: config

### Summary
Using `powershell -File` with two comma-separated values for `-EvidencePath` passed an invalid combined path to the improvement recorder.

### Error
```text
Exception calling IsPathRooted: Illegal characters in path.
```

### Context
- Operation: record one project workflow improvement.
- Cause: the array-valued `EvidencePath` parameter did not bind as intended through the command-line form.
- No improvement record was created by the failed attempt.

### Suggested Fix
Pass one sufficient evidence path, or invoke the script from PowerShell with an explicit string array rather than comma-separated `-File` arguments.

### Metadata
- Reproducible: yes
- Related Files: D:/ProgramData/CodexHome/skills/improve-ai-film-workflow/scripts/record_improvement.ps1

---
