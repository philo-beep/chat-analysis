# 上传到 GitHub

仓库骨架已经建好，本地也已初始化为 git 仓库（分支 `main`）。剩下只差把它接到你的 GitHub 仓库上。

## 方式一：仓库已建好（推荐）

在 GitHub 上新建一个**空仓库**（不要勾选 Add a README / .gitignore / license），然后：

```bash
cd C:\Users\pop\Desktop\项目
git remote add origin https://github.com/<你的账号>/<仓库名>.git
git push -u origin main
```

仓库名建议用英文（例如 `chat-analysis`），路径里有中文容易出现各种编码问题。

## 方式二：创建五个功能分支

骨架提交后，按分工建好各人的分支并推送：

```bash
git branch codex/input-history
git branch codex/result-panel
git branch codex/backend
git branch codex/ai-analysis
git branch codex/test-demo
git push origin codex/input-history codex/result-panel codex/backend codex/ai-analysis codex/test-demo
```

## 方式三：用图形化 Git 工具

不熟悉命令行也可以用 GitHub Desktop、TortoiseGit 或 VS Code 的源代码管理面板完成提交、推送，再到仓库网页创建 PR。

## 加入成员

仓库页面 → Settings → Collaborators → Add people，把五个人的账号都加进来。

## 注意事项

- 密钥、`.env`、本地数据库已被 `.gitignore` 排除，不会误传。
- 如果 GitHub 仓库里已经有内容（比如自动生成了 README），直接 push 会被拒绝，先告诉 C 处理。
