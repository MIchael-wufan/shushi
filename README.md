# division-vertical-mcp

通过 MCP（stdio）生成**网格对齐**的小学/初中风格**除法竖式** SVG；除数为小数时可绘制**移小数点等教学留痕**（强调色见 `render_config`），并可附带**验算**（乘法结果行 + 划掉多余尾零）。

## 安装

```bash
cd division-vertical-mcp
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## 在 Cursor 中注册

在 MCP 配置里增加（路径按本机修改）：

```json
{
  "mcpServers": {
    "division-vertical": {
      "command": "/绝对路径/division-vertical-mcp/.venv/bin/python",
      "args": ["-m", "division_vertical_mcp"]
    }
  }
}
```

## 部署：SVG 直出与 OSS 图片 URL

五个 MCP 工具在生成竖式后，最终返回内容由环境变量 `DIVISION_VERTICAL_MCP_SVG_OUTPUT_MODE` 控制（**默认**为 OSS 模式）：

| 值 | 行为 |
|----|------|
| `oss_img`（**默认**） | 将 SVG 上传至阿里云 OSS 后，返回可嵌入的 HTML 片段：`<br><img src="公网URL" width="Npx"><br>`。 |
| `oss_url` | 上传至 OSS 后，仅返回公网 URL 字符串（无 `<img>`）。 |
| `raw_svg` | 返回完整 UTF-8 SVG 文本（与早期仅返回 SVG 的行为一致）。 |

可选环境变量：

- `DIVISION_VERTICAL_MCP_SVG_IMG_WIDTH`：上述 `<img>` 的 `width` 数值部分，默认 `120`（即 `120px`）。

**阿里云 OSS（`oss_img` / `oss_url` 必填）**：可通过环境变量注入；或在项目根目录放置 **`.env`**（已被 `.gitignore` 忽略），启动时会自动加载，`python-dotenv` 已作为依赖安装。**勿将含密钥的 `.env` 提交到仓库。** 下列名称亦可使用无前缀别名 `OSS_ACCESS_KEY_ID`、`OSS_ENDPOINT` 等。

| 变量 | 说明 |
|------|------|
| `DIVISION_VERTICAL_OSS_ACCESS_KEY_ID` | AccessKey Id |
| `DIVISION_VERTICAL_OSS_ACCESS_KEY_SECRET` | AccessKey Secret |
| `DIVISION_VERTICAL_OSS_ENDPOINT` | SDK 连接地址，例如内网 `http://oss-cn-beijing-internal.aliyuncs.com` |
| `DIVISION_VERTICAL_OSS_BUCKET` | 桶名，例如 `apolo-image-test` |
| `DIVISION_VERTICAL_OSS_PUBLIC_BASE_URL` | 返回给客户端的公网基址（无尾部 `/` 亦可），例如 `http://apolo-image-test.oss-cn-beijing.aliyuncs.com` |

上传时使用 UTF-8 与 `Content-Type: image/svg+xml; charset=utf-8`。请确认桶或对象为**公共读**（或配合 CDN），以便 `<img src>` 可匿名 GET（详见 [docs/OSS_UPLOAD_GUIDE.md](docs/OSS_UPLOAD_GUIDE.md)）。

**详细实现步骤（函数契约、公网 URL 模式、伪代码、排错）见：[docs/OSS_UPLOAD_GUIDE.md](docs/OSS_UPLOAD_GUIDE.md)。**

## 工具说明

- **render_division_vertical**
  - `dividend` / `divisor`：字符串，支持小数（有限小数）。
  - `include_verification`：默认 `false`；为 `true` 时附加「验算」乘法块（实验性，数位对齐仍在改进）。
  - `retain_decimal_places`：可选整数 `n`（≥0）。若传入，横式「=」右侧为**四舍五入到 n 位小数**的商；竖式在移位整数除法完成后，若有余数，则继续补 0 除到商的小数部分共 **n+1 位**后停止（余数提前为 0 则提前结束）。不传则与原先一致，商为精确有限表示（无额外小数步）。
  - 默认返回 **含 `<img>` 的 HTML 片段**（见上表）；设 `raw_svg` 时返回 **UTF-8 SVG 文本**。

## 字体

- 数字与算式使用 **Latin Modern Roman**（与 TeX 系 Latin Modern 同源）。SVG 内通过 `@font-face` 从 jsDelivr 加载 `lmroman10-regular.woff`；离线环境若无法访问 CDN，请在本机安装 Latin Modern 或改写 `svg_render.py` 中的字体 URL。

## 限制

- 移位后的被除数须为**有限整数**（与教材有限小数除法一致）。
- 未传 `retain_decimal_places` 时，商仍按精确整数/有限小数表示；传入后小数竖式步在单步商位大于 9 时会报错（极少见）。
- 验算竖式为简化版（结果行 + 尾零划掉），与 TikZ 示例中的分步部分积可后续再对齐增强。

## 教学标注与进位颜色

默认不额外使用红色：与正文同为黑色。若需恢复教材式红标、红进位，在仓库内**仅**编辑 `division_vertical_mcp/render_config.py` 中两个布尔开关（文件内有说明）：

- `REMARKS_IN_RED`：除法移位留痕、补零/新小数点、验算中强调等  
- `SHOW_CARRY_BORROW_DIGITS`：为 `True` 时才**画出**进位/借位小号字（默认不画）  
- `CARRY_BORROW_IN_RED`：在**已画**出进位/借位时，是否用红色强调；仅当 `SHOW_CARRY_BORROW_DIGITS` 为 `True` 时才有意义  

`Style.color_red` 仍为 `#e02020`；仅当 `REMARKS_IN_RED` / `CARRY_BORROW_IN_RED` 为 `True` 时相关描画才用该色。

重生成 `test-3` 下全部示例 SVG 与 `index.html`（按当前 `render_config` 与算式表）：

```bash
PYTHONPATH=. python3 scripts/generate_test3_from_index.py
```
