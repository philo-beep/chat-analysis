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

## 如果连不上 github.com

现象：`git push` 卡很久，最后报

```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443
```

这是网络问题，不是命令写错了。判断方法：浏览器能打开 GitHub 网页，但 git 就是连不上——因为浏览器走系统代理，而 **git 不读系统代理**。

解决办法是让 git 走本地代理端口（把 7897 换成你自己代理软件的端口）：

```bash
# 只对当前仓库生效
git config http.proxy http://127.0.0.1:7897
git config https.proxy http://127.0.0.1:7897

# 或者对本机所有仓库生效
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

检查代理端口是否可用：

```bash
curl -s -o NUL -w "%{http_code}" -x http://127.0.0.1:7897 https://github.com
```

返回 `200` 就说明通了。

不需要代理时（比如换到能直连的网络）取消：

```bash
git config --unset http.proxy
git config --unset https.proxy
```

## 克隆到本地

新成员第一次拿到代码（仓库是私人的，需要先被加入 Collaborators）：

```bash
git clone https://github.com/philo-beep/-.git
cd -
git branch -a          # 能看到 main 和五个功能分支
```

然后按 README 的步骤安装依赖、启动前后端，确认自己这台电脑能跑起来，再开始开发。
