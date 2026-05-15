---
name: describe-image
description: Describe images via an external multimodal LLM when the primary model lacks vision capability. Use whenever the user needs to understand, analyze, or extract information from any image — screenshots, diagrams, charts, photos, tables, documents, formulas, code snippets rendered as images, etc.
---

# describe-image

Bridge to a multimodal LLM when the primary model cannot process images natively.
Invoke this skill for **any** request that involves visual understanding of an image file or URL.

## When to invoke (broad)

Invoke whenever the user:
- Provides an image path or URL and expects you to understand its content
- Asks to "see", "look at", "view", "read", "check", "describe" any image
- Wants data extracted from a chart, table, or plot in image form
- Asks about a screenshot, photo, diagram, architecture figure, or formula
- Shares a UI screenshot and asks for debugging or explanation
- Says anything that implies visual perception of a file ending in: png, jpg, jpeg, gif, webp, bmp, svg, tiff, pdf (first page as image)

**Trigger keywords (English):** see, look, view, read, describe, check, show, explain, what's in, what does this, screenshot, image, picture, photo, diagram, chart, figure, plot, visual, display, watch, observe, inspect, examine, extract from, scan, snapshot, capture

**Trigger keywords (Chinese):** 看, 读, 图, 照片, 截图, 图片, 显示, 展示, 描述, 识别, 查看, 检查, 分析, 提取, 扫描, 观察, 浏览, 显示什么, 里面有什么, 写了什么, 画了什么

If an image path/URL appears in the user message and they expect a response about its content, invoke this skill — even without explicit trigger words.

## How to invoke

```bash
python3 tools/describe-image.py --path <path>  # local file
python3 tools/describe-image.py --url <url>     # remote URL
```

## Prompt customization

The `--prompt` flag controls what the vision model focuses on. **Always tailor it to the user's intent** rather than using the default. Examples:

```bash
# Data extraction from charts/tables
python3 tools/describe-image.py --path chart.png \
  --prompt "Extract all numerical data, axis labels, and legend entries from this chart. Output as a structured table."

# Reading text from screenshots
python3 tools/describe-image.py --path screenshot.png \
  --prompt "Read all visible text, code, error messages, and UI labels in this screenshot. Preserve the exact wording."

# Debugging UI
python3 tools/describe-image.py --path ui.png \
  --prompt "Describe the UI layout, all interactive elements, any error states or anomalies visible in this screenshot."

# Formula / math
python3 tools/describe-image.py --path equation.png \
  --prompt "Transcribe all mathematical formulas and notation in this image into LaTeX. Include surrounding context."

# General description
python3 tools/describe-image.py --path photo.jpg \
  --prompt "Describe this image thoroughly. Note all objects, people, text, colors, spatial relationships, and context."

# Document scan
python3 tools/describe-image.py --path scan.png \
  --prompt "OCR all text from this document scan. Preserve paragraph structure, headings, and tables."
```

**Rule:** read the user's question carefully. If they ask about specific content (numbers, text, layout, colors), craft a prompt that targets exactly that. Use the default description prompt only when the user has no specific question.

## Thinking / reasoning mode

If the model supports chain-of-thought reasoning, enable it:

```bash
# Via CLI flag
python3 tools/describe-image.py --path chart.png --thinking

# Or via env var (applies to all invocations)
export DESCRIBE_IMAGE_THINKING=true
```

This adds `thinking: {type: "enabled"}` to the request. The reasoning trace (if returned) is captured in the `reasoning` field of the output JSON.

## Provider-specific parameters

Use the `DESCRIBE_IMAGE_EXTRA_BODY` env var to inject any custom JSON into the request body:

```bash
export DESCRIBE_IMAGE_EXTRA_BODY='{"chat_template_kwargs":{"enable_thinking":true}}'
```

## Prerequisites

```bash
export DESCRIBE_IMAGE_API_KEY="your-api-key"
export DESCRIBE_IMAGE_BASE_URL="https://your-provider.com/v1"
export DESCRIBE_IMAGE_MODEL="model-name"
```

Optional:
```bash
export DESCRIBE_IMAGE_THINKING=true       # enable COT reasoning
export DESCRIBE_IMAGE_EXTRA_BODY='{"...":"..."}'  # arbitrary extra request params
export DESCRIBE_IMAGE_TIMEOUT=120         # default: 120 seconds
```

## Output format

The tool prints a JSON object to stdout:
```json
{
  "description": "<the model's text response describing the image>",
  "model": "model-name",
  "reasoning": "<chain-of-thought trace, only if thinking enabled and model supports it>"
}
```

## Post-processing

After receiving the JSON output:
1. Present the description clearly to the user, using markdown formatting if helpful
2. If the user had a specific question, answer it based on the description
3. If data was extracted, format it as a table or list
4. If `reasoning` is present and the user asked a complex analytical question, you may summarize the reasoning
