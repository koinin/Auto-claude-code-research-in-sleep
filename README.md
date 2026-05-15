# Auto-Claude-Code-Research-in-Sleep

学术研究技能（skills）与工具（tools）的规范化管理仓库。

## 目录结构

```
.claude/skills/    # Claude Code 技能定义 (67 个)
tools/             # 配套执行脚本 (27 个)
```

## 快速开始

```bash
git clone git@github.com:koinin/Auto-claude-code-research-in-sleep.git
# 将 .claude/skills/ 和 tools/ 链接或复制到你的 scholar 项目
```

## 环境变量配置

将以下内容添加到 `~/.zshrc` 或 `~/.bashrc`，按需启用。

### 必配

```bash
# Exa 搜索
export EXA_API_KEY="your-exa-api-key"

# 图像识别 (describe-image)
export DESCRIBE_IMAGE_API_KEY="sk-your-key"
export DESCRIBE_IMAGE_BASE_URL="https://api.openai.com/v1"
export DESCRIBE_IMAGE_MODEL="gpt-4o"

# Gemini 图像生成 (paper-illustration / mermaid-diagram)
export GEMINI_API_KEY="your-gemini-key"

# OpenAI (多个 skill 依赖)
export OPENAI_API_KEY="sk-your-key"
```

### 推荐配置

```bash
# Semantic Scholar (提升请求频率限制)
export SEMANTIC_SCHOLAR_API_KEY="your-key"

# OpenAlex (optional, 提高请求限额)
export OPENALEX_API_KEY="your-key"
export OPENALEX_EMAIL="your@email.com"

# W&B 实验追踪
export WANDB_API_KEY="your-wandb-key"

# HuggingFace (Modal 部署用)
export HF_TOKEN="hf_your-token"
```

### describe-image 可选配置

```bash
export DESCRIBE_IMAGE_THINKING=true          # 启用 chain-of-thought
export DESCRIBE_IMAGE_EXTRA_BODY='{}'        # 注入自定义请求参数
export DESCRIBE_IMAGE_TIMEOUT=120            # 请求超时 (默认 120s)
```

### 平台特定

```bash
# 启智平台 (qzcli)
export QZCLI_USERNAME="your_username"
export QZCLI_PASSWORD="your_password"
export QZCLI_API_URL="https://qz.yourorg.edu.cn"

# 论文验证
export ARIS_VERIFY_EMAIL="your@email.com"
```

## 安装

```bash
pip install exa-py deepxiv-sdk requests
```

## 开发

```bash
# 添加新 skill
mkdir -p .claude/skills/my-skill
cp SKILL.md .claude/skills/my-skill/

# 添加新 tool
cp my_tool.py tools/

# 提交
git add -A && git commit -m "feat: add my-skill" && git push
```
