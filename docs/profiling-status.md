# 分析计时工具状态

2026-10-20：计时和提速现已实施，结果与局限见 [分析提速交付报告](analysis-speed-delivery.md)。下文保留首次计时工具交付时的状态说明。

`backend/tests/profile_analysis.py` 临时注入分阶段计时，调用真实 `/analyze`，仅使用临时数据库；不被正式服务导入，不改变模型、推理强度、复核、结果结构或事务。

工具自检通过，`docs/evidence/profiling/instrumentation-check.json` 中 `dry_run=true`，表示模型替身自检，**不是云端性能基线**。首次两次真实测试启动因工具权限审核超时未执行；后续用户授权直接执行，已取得文字/截图基线及优化验证，见上述报告。

在项目根目录手动测量（需要本机已有云端凭据）：

```powershell
.\backend\.venv\Scripts\python.exe -B -u backend/tests/profile_analysis.py text --limit 90
.\backend\.venv\Scripts\python.exe -B -u backend/tests/profile_analysis.py image --limit 90
```

每项90秒硬上限，超时停止。不要把嵌套阶段耗时重复相加。等待用户查看实际计时后，再确定优化顺序。
