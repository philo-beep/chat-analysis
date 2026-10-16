# GitHub 网络与仓库维护

克隆、提交、上传的**具体步骤**在 [docs/workflow.md](workflow.md)。
这份文件只讲两件事：连不上 GitHub 怎么办，以及仓库本身怎么维护。

仓库地址：`https://github.com/philo-beep/chat-analysis`（私有）

---

# 一、如果连不上 github.com

现象：`git clone` 或 `git push` 卡很久，最后报

```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443
```

这是网络问题，不是命令写错了。判断方法：浏览器能打开 GitHub 网页，但 git 就是连不上——
因为浏览器走系统代理，而 **git 不读系统代理**。

让 git 走本地代理端口（`7897` 换成你自己代理软件的端口，每个人不一样）：

```bash
git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897
```

**必须用 `--global`**，因为 `git clone` 之前本地还没有仓库，仓库级配置那时候不存在，
只有全局配置才管用。

先确认端口对不对，再配：

```bash
curl -s -o NUL -w "%{http_code}" -x http://127.0.0.1:7897 https://github.com
```

返回 `200` 就说明这条路通了。返回 `000` 说明端口填错了，或者代理软件没开。

换到能直连的网络后想取消：

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

> 注意：不要照抄别人的端口。每个人的代理软件不一样，端口也不一样。

---

# 二、如果你在仓库改名之前就克隆过

仓库地址从 `philo-beep/-` 改成了 `philo-beep/chat-analysis`。GitHub 会把旧地址自动跳转，
**不改也能继续用**，但建议改掉，免得以后报错信息看着奇怪：

```bash
git remote set-url origin https://github.com/philo-beep/chat-analysis.git
git remote -v          # 确认显示的是新地址
```

---

# 三、仓库维护（C 用）

## 加人、移人、改权限

仓库页面 → Settings → Collaborators → Add people。默认给 **Write** 就够：
能推自己的分支、能发 PR、能评论；不能改仓库设置、不能删仓库、不能加人。

谁退出项目了就移掉，之后他本机就推不上来了。

## 待接受的邀请

邀请发出去之后对方**必须自己点接受**。没接受的表现在这里看：
Settings → Collaborators 里的 Pending invitations。

对方如果还没接受就克隆，报的错是 `Repository not found`——看起来像地址写错了，
其实是没有权限，这一点非常容易误判。

## 密钥不进仓库

密钥写在各自电脑的 `backend/.env` 里（复制 `backend/.env.example` 得到），
`.env` 已经被 `.gitignore` 排除，提交不上去。**不要把密钥贴到代码、聊天记录或截图里。**

## main 分支加不了保护规则

免费账号的私有仓库不支持分支保护（GitHub 会提示要升级 Pro 或改成公开仓库）。
所以"谁都不直接推 main"只能靠约定，见 [docs/workflow.md](workflow.md)。

## 合并 PR 之后不要点 Delete branch

`codex/xxx` 是每个人长期使用的分支，不是一次性分支。删掉之后对方下次推送会把分支重新建回来，
或者直接报错，白折腾一轮。
