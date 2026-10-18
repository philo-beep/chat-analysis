# 日常协作操作手册

**目标**：每个人在自己电脑上改代码，上传后其他人能看见；任何时候都能在本地跑起完整项目。

## 本项目 Agent 的推送确认规则（2026-10-18 用户追加）

以下规则优先于后文的日常操作示例。每次准备推送均须重新执行，之前的确认不自动授权下一次推送。

1. 检查 `git status`、当前分支、`git remote -v` 和未完成的 merge/rebase。存在未解决冲突时，先报告冲突，不重复执行 pull。用户的编辑器状态、数据库、配置等文件不能混入提交。
2. 在当前功能分支执行 `git pull --no-rebase origin <当前功能分支>`，审查此次拉取的队友提交与差异。如果远端尚无该分支，先拉取 `origin main` 并说明该分支是首次推送。不要自动 rebase 已共享的提交。
3. 发生冲突时，列出文件、位置、双方差异、可选合并方案及推荐方案，等待用户确认。不得使用强制推送，或直接以整份本地/远端文件覆盖冲突。
4. 无冲突或获批解决后，运行该改动需要的自检。向用户展示拟推送分支、提交、测试结果以及远端同步情况，等待明确确认后再执行 push。
5. 等待期间如果远端发生变化，应重新同步、检查和自测；发现新冲突重新请求确认。推送拒绝时先查原因，禁止自动循环重试或加 `--force`。

冲突方案的确认仅授权处理该次冲突，不能代替之后的推送确认。远端同步不产生文字冲突，也仍需验证组合后的功能。

## 分支分工

| 分支 | 负责人 | 主要改这些文件 |
| --- | --- | --- |
| `main` | 全组 | **不要直接提交**，只通过 PR 合并进来 |
| `codex/input-history` | A | App.vue、ChatInput.vue、RecordList.vue、api.js |
| `codex/result-panel` | B | components/ResultPanel.vue |
| `codex/backend` | C | backend/main.py、backend/database.py、docs/api.md |
| `codex/ai-analysis` | D | backend/ai_service.py |
| `codex/test-demo` | E | samples/、docs/acceptance.md |

---

# 一、只做一次的准备工作

## 1. 接受邀请

在邮箱里找到 GitHub 发来的邀请邮件，点 **View invitation → Accept invitation**。
手机上不好操作的话，直接打开 `https://github.com/philo-beep/chat-analysis` 的邀请链接也行。

> **没接受邀请之前，克隆会报 404，或者一直让你输密码。** 这一步必须在克隆之前完成。

结果：你成为仓库成员，网页上能看到仓库，可以克隆和推送。

## 2. 连不上 GitHub 才需要：配代理

先测一下：

```bash
curl -s -o NUL -w "%{http_code}" https://github.com
```

返回 `200` 就跳过这步。如果卡住不动、或者报 `Failed to connect to github.com`，
说明要走代理——配法在 [docs/github.md](github.md) 的「如果连不上 github.com」一节。

**这一步要在克隆之前做完**，配好再回来继续。

## 3. 克隆仓库

```bash
git clone https://github.com/philo-beep/chat-analysis.git
cd chat-analysis
```

结果：本地多出一个 `chat-analysis` 文件夹，里面是完整项目，并且自动停在 `main` 分支。

不习惯命令行也可以用 GitHub Desktop、TortoiseGit 或 VS Code 的源代码管理面板，
只需要仓库地址，登录用你自己的 GitHub 账号。

## 4. 切到自己的分支

```bash
git checkout codex/input-history     # 换成你自己那个分支
```

结果：提示 `Switched to a new branch 'codex/input-history'`。你现在在自己的分支上，改代码不会影响别人。

## 5. 确认自己能跑起来

按 [README](../README.md) 的步骤装依赖、启动前后端。

结果：浏览器能打开页面，输入一段聊天能出分析结果（现阶段是明确标注过的开发样例）。

**这一步通过了再开始写代码。** 否则会出现「大家都在改一个自己跑不起来的环境」这种最麻烦的情况。

---

# 二、每天的工作循环

## 第 1 步：动手前先同步

```bash
git checkout main                    # 回到公共分支
git pull                             # 拉下别人已合并的成果
git checkout codex/input-history     # 回自己的分支
git merge main                       # 把最新 main 合进自己的分支
```

结果：你的分支里包含了全组最新的代码，你自己已写的内容不会被覆盖。

**每次开始干活前都要做这一步。** 冲突几乎都来自「好几天没同步，一合并全是冲突」。

## 第 2 步：改代码，本地运行

只改自己负责的文件。改完在本地跑一遍，确认没把原来的功能弄坏。

结果：改动只存在于你自己的硬盘上，别人看不到。

## 第 3 步：提交

```bash
git status                    # 先看一眼改了哪些文件，确认没有多余文件混进来
git add <本次任务的文件路径>     # 逐项暂存；不要混入他人的未提交修改
git commit -m "结果面板支持修改需求和复制回复"
```

结果：改动被记成一个「提交」，**但依然只在你自己的电脑上**。GitHub 上看不到，别人也看不到。

想确认这一点：`git log --oneline -1` 显示的版本号和 `git ls-remote origin codex/input-history` 显示的版本号是不一样的。

## 第 4 步：同步、自检，取得确认后上传

按文首规则先在当前功能分支拉取并审查差异。下例中的分支要换成当前分支，不能照抄其他人的分支：

```bash
git pull --no-rebase origin codex/input-history
git status
git diff --check
```

执行对应模块的检查；出现冲突按文首规则提交方案并等待。没有冲突且自检通过后，先向用户报告并等待推送确认。取得确认才执行：

```bash
git push
```

结果：GitHub 上你那个分支跳到最新版本，**全组都能看到了**。

第一次推送会弹出浏览器让你登录 GitHub，登录一次之后就不用再登了。

## 第 5 步：做完一个完整的小功能，发 PR

在 GitHub 仓库页面点 **Pull requests → New pull request**，`base` 选 `main`，`compare` 选你自己的分支。

标题写清楚做了什么，描述里写上**怎么验证**，最好附操作截图。例如：

> 结果面板支持修改需求和复制回复。验证：输入聊天 → 分析 → 改需求文本 → 复制回复，粘贴出来是改后的内容。

结果：全组能看到你的改动、能在 PR 里评论；PR 由 C 合并到 `main`（C 自己的 PR 由另一名技术成员合并）。合并之后所有人 `git pull` 就能拿到你的代码。

**一个 PR 只处理一件相对完整的事**，不要攒一周再发一个巨大的 PR。

---

# 三、怎么看别人干了什么

## 方式一：GitHub 网页（最直观）

| 想看什么 | 点哪里 |
| --- | --- |
| 谁最近提交了什么 | 仓库首页 → Commits，或右侧 Recent activity |
| 每个分支各自到哪一步了 | 仓库首页 → 左上角分支下拉框 |
| 谁在做哪件事、进度如何 | **Pull requests** 标签页（最有用，一眼看出谁在等谁） |
| 某个文件最近被谁改过 | 打开文件 → 右上角 History |

## 方式二：命令行

```bash
git fetch --all            # 抓取所有分支的最新情况；只是"看情报"，不动你的代码
git log --oneline --all --graph --decorate
```

结果：打印一张全组的提交图，能看到每个分支停在哪个提交上。

> `git fetch` 和 `git pull` 的区别：`fetch` 只看不改，`pull` 会真的把内容合进你当前分支。不确定的时候先用 `fetch`。

---

# 四、推送被拒绝怎么办

现象：

```
! [rejected]  main -> main (non-fast-forward)
```

原因：你上传之前，别人已经往同一个分支推过东西，或者你在网页上直接改过文件。

先检查当前分支、工作区和远端差异。已有合并或变基未完成时，不要再发起新的 pull。工作区可安全同步时：

```bash
git fetch origin
git log --oneline HEAD..origin/<当前分支>
git diff HEAD...origin/<当前分支>
git pull --no-rebase origin <当前分支>
```

如果提示冲突：

```
CONFLICT (content): Merge conflict in frontend/src/components/ResultPanel.vue
```

**不要自己乱删文件，也不要直接采用整份本地或远端版本。** 列出冲突位置、双方差异和方案，推荐保留双方有效功能的处理方法，等待用户确认后再解决。按分工表，`ResultPanel.vue` 是 B 负责，`backend/` 是 C 负责。

解决后重新测试，再等待用户对本次推送的确认；不要把“同意解决冲突”解释为“同意推送”。

---

# 五、操作对照表

| 你做的操作 | 会发生什么 | 影响范围 |
| --- | --- | --- |
| `git clone` | 本地多一份完整项目副本 | 只有你自己 |
| `git checkout <分支>` | 切换工作分支，文件变成该分支的样子 | 只有你自己 |
| 直接改文件 | 只是硬盘上的文字变化 | 只有你自己 |
| `git add` + `git commit` | 记成一个提交，仍在本地 | 只有你自己 |
| `git push` | GitHub 上你的分支更新，全组可拉取 | **全组可见** |
| `git fetch` | 只更新远端分支的"情报"，不动你的代码 | 只有你自己 |
| `git pull` | 把远端最新内容合进你当前分支 | 只有你自己 |
| 发 PR | 全组看到你的改动，可以评论 | **全组可见** |
| 合并 PR | `main` 前进，别人 `git pull` 能拿到 | **全组可见** |

一句话总结：**`commit` 是存到自己电脑，`push` 才是给全组看。**
