# FlaskToolkit v4.23.2

版本检查强制语义收紧（`tools/update.py check --force`），全量回归 49 脚本 0 失败。

## 收紧版本检查「强制检查」语义

框架版本检查（`core/update_checker.py`）与 CLI（`tools/update.py check`）原本已支持 `force` 跳过缓存有效期，但 `check_for_update(force=True)` 在**网络 / 解析失败时仍会回退返回过期缓存**，导致：

- 执行 `python tools/update.py check --force` 时，若数据源连不上，仍被当作「已检查到最新版本」，没有真正做到「忽视缓存有效期」；
- 后台 / 手动强制检查在失败时可能返回旧数据，调用方无法感知强制检查失败。

修复后语义（v4.23.2）：
- **force 强制检查**：跳过缓存有效期立即重新拉取数据源；网络/解析失败时**不回退过期缓存**，明确返回检查失败（`update_checker` 打 `warning` 留痕，`update.py check` 打印「检查失败」并返回非零）。
- **非 force 检查**：保持不变，网络/解析失败仍静默回退旧缓存（有则），保证启动可用性不报错。

## CLI 参数说明

`tools/update.py check` 的 `--force` 参数说明已明确：

```bash
python tools/update.py check              # 检查新版本（changelog.json 数据源，24h TTL）
python tools/update.py check --force      # 强制检查：忽略缓存有效期，立即重新拉取数据源（拉取失败不回退缓存）
```

## 测试与文档

- 新增 3 项回归断言：`test_update_checker.py`（force 强制检查失败不回退过期缓存 / 非 force 失败仍回退旧缓存）。
- README 双版断言 1330→**1333**；dev guide 十二章 `test_update_checker` 52→55 项，并补充 14.5 节 `check --force` 说明。

**全量回归 49 脚本 0 失败。**

- **Runtime**: `FlaskToolkit-4.23.2-runtime.zip`（精简运行包）
- **sha256**: `c15573f7eb742b0dcacd2daa9e36d55d8d123047a2932941929c0825c36fc147`
