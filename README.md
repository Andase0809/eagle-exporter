# Eagle Exporter v1

Eagle Exporter 是一个面向 Eagle 素材库的桌面导出工具，用于从 Eagle `.library` 或 `images` 目录读取素材元数据，并批量整理为 Excel、Markdown 或 JSON 文件。

它适合把素材标题、描述、话题标签、缩略图和分类信息转成可交付、可检索、可二次处理的内容资产列表。

## 功能

- 扫描 Eagle `.library` 或 `images` 目录
- 读取素材 `metadata.json` 与缩略图
- 按 Eagle 文件夹分类聚合素材
- 解析小红书话题、普通 hashtag 和常见账号标签
- 导出带缩略图的 Excel 表格
- 导出 Markdown 文案清单
- 可选导出结构化 JSON
- 保存本机路径、导出格式、主题和线程数等偏好配置

## 项目结构

```text
eagle-exporter
├─ eagle_exporter/
│  ├─ app.py
│  ├─ config.py
│  ├─ models.py
│  ├─ services/
│  │  ├─ scanner.py
│  │  └─ exporters.py
│  ├─ ui/
│  │  └─ main_window.py
│  └─ utils/
│     └─ logging_utils.py
├─ tests/
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

## 安装

建议使用虚拟环境：

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

也可以只安装运行依赖：

```bash
python -m pip install -r requirements.txt
```

## 运行

源码方式运行：

```bash
python -m eagle_exporter.app
```

安装后也可以使用命令行入口：

```bash
eagle-exporter
```

打开界面后选择 Eagle 资源库目录和导出目录，先扫描资源库，再选择需要导出的分类和格式。

## 数据边界

- 本工具只读取本地 Eagle 资源库文件，不上传素材或元数据。
- 配置文件 `eagle_exporter/eagle_config.json` 只保存在本机，已默认加入 `.gitignore`。
- JSON 导出中可能包含本机素材路径，公开分享前请自行脱敏。
- 导出的 Excel、Markdown、JSON 文件默认不应提交到公开仓库。

## 测试

```bash
python -m pytest -q --basetemp .pytest-tmp
```

测试覆盖扫描路径识别、元数据解析、话题提取、去重、Excel/Markdown/JSON 导出和工作表名称清洗等核心逻辑。
