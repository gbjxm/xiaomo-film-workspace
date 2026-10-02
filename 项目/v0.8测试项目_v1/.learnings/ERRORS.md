# Errors

Command failures and integration errors.

---

## [ERR-20260820-001] isolated-install-log-redirection

**Logged**: 2026-08-20T13:15:00+08:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
隔离安装验证在安装器启动前失败，因为输出重定向目标目录尚未创建。

### Error

```text
Could not find a part of the path ...\isolated-install-v4\install-output.txt
```

### Context

- 操作：把安装器输出写入新隔离目录中的日志文件。
- 影响：安装器未启动；候选、正式源和正式安装均未改变。

### Suggested Fix

先创建隔离测试根目录，再执行带文件重定向的安装与 VerifyOnly。

### Metadata

- Reproducible: yes
- Related Files: 验证/isolated-install-v4

### Resolution

- **Resolved**: 2026-08-20T13:15:00+08:00
- **Notes**: 后续命令在重定向前显式建立隔离目录。

---
