# 实现 OSS 上传并获取 SVG 公网地址：详细方案指导

本文说明如何在 `division_vertical_mcp/oss_store.py` 中实现 `upload_svg_get_public_url`，使 MCP 工具在 **默认 `oss_img` 模式**下，将内存中生成的竖式 **SVG 文本**上传到公司对象存储，并返回**浏览器 / Confluence `<img src>` 可直接使用**的 URL。

---

## 1. 目标与数据流（本仓库已具备的部分）

**生成 SVG**  
`compose` / `svg_render` 等已在内存中产出**完整 UTF-8 字符串**（含 `<svg xmlns=...>`），**不会**先写本地 `*.svg` 文件。

**输出分支**  
`server.py` 中各工具在 `return` 前调用 `mcp_svg_text_to_tool_output(svg_string)`。

**OSS 模式**  
当 `DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE` 为 **oss_img**（默认）时，会调用 `upload_svg_get_public_url(svg_text, object_key=...)`，再包装为 `<br><img src="公网URL" width="Npx"><br>`。

**待实现**  
**仅** `upload_svg_get_public_url` 内部：把 `svg_text` 作为对象体 `PUT` 到 OSS，并**返回**字符串 URL。

**结论**：你要实现的是「**字节流上传 + 得到可访问的 URL**」，输入是 **Python `str`（UTF-8 文本）**，不是必须先落盘；若 SDK 只支持文件路径，再在你写的函数里用 `tempfile` 写临时文件，上传后删除即可。

---

## 2. 必须满足的函数契约

- **位置**：`division_vertical_mcp/oss_store.py`  
- **注意**：勿随意改参数名/语义，避免与 `mcp_svg_text_to_tool_output` 调用处不一致。

函数签名如下：

```python
def upload_svg_get_public_url(
    svg_text: str, *, object_key: str | None = None, content_type: str = "image/svg+xml"
) -> str:
```

**入参 `svg_text`**  
整段 SVG 文本；实现里应使用 **UTF-8 编码**上传（`svg_text.encode("utf-8")`）。

**入参 `object_key`**  
对象在桶内的路径/键。若 `None`，调用方会传 `division-vertical-mcp/<uuid>.svg`（见 `_default_object_key`）。可固定加业务前缀，例如 `prod/division-vertical-mcp/xxx.svg`。

**入参 `content_type`**  
建议与 OSS 侧 `Content-Type` 一致。常用值：`image/svg+xml` 或 `image/svg+xml; charset=utf-8`。

**返回值**  
**必须**为以 `http://` 或 `https://` 开头的**完整 URL 字符串**；`mcp_svg_text_to_tool_output` 会校验，否则抛 `ValueError`。

**禁止**  
返回相对路径、仅 path、无协议的域名等。

实现完成后，**删除**函数体内的 `raise NotImplementedError(...)`，改为真实上传与 `return`。

---

## 3. 公网 URL 的两种常见模式

根据公司安全策略二选一或组合使用。

### 3.1 公共读桶 + 固定域名（适合内嵌 `<img>`）

- 桶或对象 ACL 为**公共读**（或经公司 CDN 对匿名开放 GET）。
- 返回 URL 形式示例：`https://your-cdn-or-oss-domain/bucket/prefix/division-vertical-mcp/xxx.svg`
- **优点**：URL 简单、无过期、适合 Confluence 长期展示。  
- **缺点**：链接泄露则任何人可访问；需按数据分级做权限与路径规范。

### 3.2 预签名 URL（适合私有桶）

- 上传后，用 SDK 生成**带过期时间的 GET 预签名 URL**。  
- **注意**：MCP 返回的 HTML 若被缓存，链接过期后图片会失效。若需长期展示，要配合**较长过期**或**定期刷新**策略，或仍采用公共读 + 不可猜测的长随机路径。  
- 若用预签名，需在文档中写清**过期时间**与运维预期。

**Confluence / 浏览器 `<img src>`**  
两种 URL 在技术上都可用的前提是：**客户端（浏览器/渲染服务）能对该 URL 发起 GET 并拿到 `image/svg+xml` 体**。若内网 Confluence 访问外网 OSS 受限，需把 OSS 或 CDN 放在**可达**的网络区。

---

## 4. 实现步骤（推荐顺序）

1. **确认厂商与凭证**  
   阿里云 OSS、华为 OBS、腾讯云 COS、MinIO、AWS S3 等；拿到 **Endpoint、AccessKey/Secret 或临时凭证、Bucket 名、地域**。**不要**把密钥写进代码仓库；用环境变量或 K8s Secret 注入（见第 6 节）。

2. **安装官方 SDK**  
   在 `pyproject.toml` 的 `dependencies` 中增加对应包（如 `oss2` 是阿里云对象存储 Python SDK 的常见包名示例，**以你司实际技术栈为准**）。执行 `pip install -e .` 更新环境。

3. **在 `upload_svg_get_public_url` 内**  
   - 解析 `object_key`：若为 `None`，可调用本模块的 `_default_object_key()` 或自写 `prefix/xxx.svg`。  
   - `body = svg_text.encode("utf-8")`。  
   - 调 SDK：`put_object` / `upload` 到指定 bucket 与 key，**设置 Content-Type**。  
   - 拼接**或**用 SDK 生成**公网 URL 字符串**并 `return`。

4. **自测**  
   - 本地或测试桶：`export DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=oss_img`，调用任一条 MCP 工具。  
   - 返回体应为 `<br><img src="https://..." width="..."><br>`。  
   - 在浏览器**新开标签**打开 `src` 的 URL，应能直接看到图形（或下载为 SVG）。

5. **与 `raw_svg` 切换**  
   联调前可设 `DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`，不走路径上传，只验证竖式业务逻辑。

---

## 5. 参考实现骨架（伪代码，按厂商替换）

```python
import os

def upload_svg_get_public_url(
    svg_text: str, *, object_key: str | None = None, content_type: str = "image/svg+xml"
) -> str:
    if object_key is None:
        object_key = _default_object_key()  # 同模块内已有

    # 从环境读配置（示例名，请改为贵司实际变量名）
    bucket = os.environ["OSS_BUCKET"]
    public_base = os.environ["OSS_PUBLIC_HTTPS_BASE"].rstrip("/")
    # public_base 示例: https://img.example.com 或 https://bucket.oss-cn-hangzhou.aliyuncs.com

    data = svg_text.encode("utf-8")

    # === 使用贵司 SDK 上传，例如伪接口 ===
    # client.put_object(Bucket=bucket, Key=object_key, Body=data, ContentType=content_type)
    # ======================================

    return f"{public_base}/{object_key}"  # 或 SDK 返回的 location；必须 https?:// 完整 URL
```

**要点**

- **路径分隔**：部分厂商 `object_key` 不含前导 `/`，而 URL 拼接时可能需要统一（避免双斜杠，可用 `urllib.parse.urljoin` 等）。  
- **中文或特殊字符**：key 中若需保留中文，需确认是否要做 URL 编码；当前默认 key 为 **hex + `.svg`**，可规避大部分问题。

---

## 6. 环境变量与密钥管理（建议）

- **AccessKey/Secret**  
  通过进程环境、Docker/K8s Secret 注入，**不**提交到 Git。

- **`.env`（本地）**  
  可 `.env` + `python-dotenv`（需自行接）；生产用编排平台管理。

- **权限**  
  用**最小权限**子账号/STS；仅对目标 bucket 有 `PutObject`；若公共读，确认是否单独配置 `GetObject` 于 CDN/OSS 策略。

可在 README 或内部 Wiki 中列出：部署 `division-vertical-mcp` 所需的所有 OSS 相关**环境变量清单**（不要写具体密钥值）。

---

## 7. Content-Type 与内容安全

- **Content-Type**：`image/svg+xml` 或 `image/svg+xml; charset=utf-8`。部分客户端对类型敏感，错误类型可能导致不渲染。  
- **SVG 内容**：当前生成的是教学用静态竖式，无脚本；若以后 SVG 中引入外链资源，需单独评估。

---

## 8. CORS（何时需要）

- 若**仅**在 Confluence/服务端渲染的页面里用 `<img src="https://oss-...">`：**通常**是简单 GET，**不触发**需预检的复杂 CORS（跨域读图片）。  
- 若前端 JS 要 `fetch` 拉 SVG 再内联，则需在 OSS/CDN 上为对应 Origin 配 **CORS 规则**。

以实际浏览器控制台报跨域为准。

---

## 9. 排错清单

- **出现 `NotImplementedError`**  
  尚未实现 `upload_svg_get_public_url`，或函数体仍保留 `raise`。

- **MCP 报 `ValueError`（与 URL 相关）**  
  返回值不是以 `http://` 或 `https://` 开头。

- **浏览器能打开 URL，但 Confluence 不显示**  
  内网策略拦截外网、HTTPS 证书、或需白名单。

- **图片裂图**  
  403/404：权限或 key 错误；或预签名已过期。

- **中文乱码**  
  上传时未用 UTF-8 编码。

---

## 10. 与 README 的交叉引用

- 环境变量 `DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE` / `DIVISION_VERTICAL_MCP_SVG_IMG_WIDTH` 的语义见仓库根目录 **README.md**「部署：SVG 直出与 OSS 图片 URL」。  
- 开发阶段仅要 SVG 文本、不接 OSS：设置 `DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE=raw_svg`。

---

**文档版本**：与仓库 `oss_store.py` 行为一致；若以后函数签名有变更，请同步更新本文件。
