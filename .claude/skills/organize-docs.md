# 整理 Wallace 设计文档版本

## 触发条件

用户要求整理 doc 目录下的 wallace 版本文档，或新增了一个新版本的设计文档（如 `wallace-v5.md`）。

## 执行步骤

### 1. 扫描当前文档

列出 `doc/` 下所有 `wallace-v*.md` 文件，识别：
- 最新版本号（数值最大的，如 v4.2 > v4.1 > v4）
- 对应的附属文件（如 `wallace-v4.2-purchase-list.md`、`wallace-v4.2-purchase-list-checked.md`）
- 旧版本文件列表

### 2. 归档旧版本

将**非最新版本**的所有文件移入 `doc/archive/`：

```bash
mkdir -p doc/archive
git mv doc/wallace-v{旧版本}.md doc/archive/
git mv doc/wallace-v{旧版本}-purchase-list*.md doc/archive/  # 如果存在
```

注意：最新版本的附属文件中，只保留最完整的采购清单（优先 `-checked` 版本），其余也归档。

### 3. 重命名最新版本为通用名

```bash
git mv doc/wallace-v{最新版本}.md doc/spec.md
git mv doc/wallace-v{最新版本}-purchase-list-checked.md doc/purchase-list.md  # 如果存在 checked 版本
# 否则：git mv doc/wallace-v{最新版本}-purchase-list.md doc/purchase-list.md
```

如果 `doc/spec.md` 和 `doc/purchase-list.md` 已经存在（说明之前已执行过整理），则：
- 将当前的 `doc/spec.md` 归档为 `doc/archive/wallace-v{旧版本号}.md`（旧版本号从文件内容的标题中提取）
- 将当前的 `doc/purchase-list.md` 归档为 `doc/archive/wallace-v{旧版本号}-purchase-list.md`
- 再将新版本文件重命名为 `doc/spec.md` 和 `doc/purchase-list.md`

### 4. 更新文件内标题中的版本号

确认 `doc/spec.md` 文件开头包含明确的版本标识，例如：
```markdown
# Wallace 技术规格 v4.2
```
如果原文件标题格式不同，不要强改，保持原样即可。

### 5. 更新 CLAUDE.md 中的版本引用

在 `CLAUDE.md` 中找到引用旧文档路径的地方，更新为新路径：
- `doc/wallace-v*.md` → `doc/spec.md`
- `doc/wallace-v*-purchase-list*.md` → `doc/purchase-list.md`
- 更新版本号描述（如 "v4.1" → 实际最新版本号）

### 6. 更新 README 或其他引用（如有）

搜索整个仓库中对旧文件名的引用，全部更新为新路径。

### 7. 验证

- 确认 `doc/spec.md` 存在且内容正确
- 确认 `doc/purchase-list.md` 存在且内容正确
- 确认 `doc/archive/` 中包含所有旧版本
- 确认没有残留的 `doc/wallace-v*.md` 文件（archive 目录除外）
- 列出最终的 `doc/` 目录结构供用户确认

## 版本迭代场景

当用户新建了 `doc/wallace-v{新版本}.md` 后调用此 skill：

1. 从当前 `doc/spec.md` 头部提取旧版本号
2. 将 `doc/spec.md` 归档为 `doc/archive/wallace-v{旧版本号}.md`
3. 将 `doc/purchase-list.md`（如存在）归档为 `doc/archive/wallace-v{旧版本号}-purchase-list.md`
4. 将新版本文件重命名为 `doc/spec.md`
5. 处理新版本附属的采购清单（如有）
6. 更新 CLAUDE.md 中的版本号
7. 用 `git mv` 执行所有文件移动以保留 git 历史

## 注意事项

- 所有文件移动使用 `git mv` 以保留 git 历史
- `doc/电子器件分类汇总.md` 不受此 skill 影响，保持原位
- 归档是单向的，不要从 archive 中恢复文件
- 执行完毕后不要自动 commit，让用户决定何时提交
