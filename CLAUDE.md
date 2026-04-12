# QuantAI 项目记忆

## 用户偏好
- 终端操作直接通过 Antigravity IDE（全权限）完成，不要每次都问用户
- 用户名: jianxiong，机器: jianxiongdeMacBook-Air
- 项目路径（本机）: ~/codes/quant-ai

## Git 操作流程（重要）
- sandbox 环境无法直接 git push（没有 GitHub 认证，网络受限）
- 正确做法：在 sandbox 中完成 git add + git commit（用 `-c user.name/email` 内联身份），然后通过 **Antigravity 命令面板**（Cmd+Shift+P → "Git: Push"）推送到 GitHub
- Antigravity 内置 Git 集成已配置好 GitHub 认证，push 走 IDE 通道无需额外认证
- 终端 `git push` 命令会卡住（HTTPS 认证问题），不要用终端 push
- GitHub 远程: https://github.com/jx1100370217/quant-ai.git (HTTPS)
- commit 身份: `-c user.name="jx1100370217" -c user.email="jx1100370217@users.noreply.github.com"`
- gh CLI 未安装，不要尝试使用

## 项目概况
- A股反转因子量化选股系统
- 后端: FastAPI (Python 3.10+) 端口 8000
- 前端: Next.js 14 端口 3000
- LLM: Claude Sonnet 4.6 (Anthropic OAuth)
- 数据源: 东方财富 API (push2.eastmoney.com)
- GitHub: https://github.com/jx1100370217/quant-ai.git

## 核心策略
- v2.0: 反转因子策略（近5日跌幅3-8%的股票均值回归）
- v1.0: 16位AI投资大师动量策略（已保留用于持仓分析）

## 已知问题
- 东方财富板块排行API (fs=m:90+t:2) 在非交易时段（周末/节假日）会断开连接
- 解决方案: 四级容错 push2→datacenter→新浪财经→本地JSON持久化缓存(7天)
- 前端fetch东方财富API受系统代理影响，已改为通过后端代理（trust_env=False）
- aiohttp需要 trust_env=False 绕过本地代理

## 技术备忘
- 后端用 watchfiles 自动重载，代码改动会自动生效
- LLM max_tokens 不要超过 4096，否则触发流式超时错误
- 全A股分页扫描每页100只，总500只（东方财富单页上限100）
- 板块缓存文件: backend/cache/sector_ranking.json
