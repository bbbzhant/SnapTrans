# 闪译 (SnapTrans) v1.0

一个 Windows 桌面工具：按全局快捷键 → 框选屏幕区域或选择窗口 → 调用视觉大模型翻译图中文字 → 在屏幕置顶小窗显示译文。专为游戏内即时翻译设计。

## 功能特点

- **全局热键截图**：按 `Ctrl+Alt+Q`（可自定义）随时截取屏幕内容，兼容大多数程序
- **两种选择模式**：
  - **框选区域**：拖拽选择屏幕上任意矩形区域
  - **窗口选择**：单击选中某个窗口，自动截取该窗口内容
- **记住上次选择**：翻译后自动记住区域/窗口，下次按热键直接翻译同一目标，无需重复选择
- **视觉大模型翻译**：截图直接发给支持视觉的 OpenAI 兼容 API，不依赖本地 OCR
- **置顶结果小窗**：半透明置顶窗口显示译文，可拖动，可设自动关闭
- **系统托盘常驻**：后台运行，右键菜单提供翻译 / 重新选择 / 设置 / 退出
- **完善的错误处理**：网络超时、Key 无效、余额不足等均在小窗中以红色文字提示，程序不崩溃
- **黑屏检测**：独占全屏 DirectX 游戏截图为黑屏时，提示切换无边框窗口模式
- **单文件 exe**：PyInstaller 打包，双击即用，无需安装 Python 环境
- **所有配置可视化**：设置界面填写 API Key / Base URL / 模型 / 语言 / 快捷键 / 透明度等，保存到 exe 同目录的 config.json

## 快速开始

### 方式一：直接使用 exe（推荐）

1. 双击 `闪译.exe`，首次启动会自动弹出设置界面
2. 填写 API Key、Base URL、模型名，保存
3. 按 `Ctrl+Alt+Q` 截图翻译

### 方式二：从源码运行

```bash
# 需要 Python 3.12+，推荐使用 uv
cd SnapTrans
uv venv
uv pip install -r requirements.txt
python main.py
```

> 注意：`config.json` 保存在脚本/exe 同目录，包含 API Key，已被 .gitignore 排除。

## 配置说明

首次运行自动弹出设置界面，所有配置保存在 exe 同目录的 `config.json`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| API Key | 你的 API 密钥 | （空） |
| Base URL | API 地址，兼容任何 OpenAI 格式服务 | `https://api.openai.com/v1` |
| 模型 | 需要具有视觉能力的大模型 | `gpt-4o-mini` |
| 目标语言 | 翻译目标语言 | `简体中文` |
| 快捷键 | 触发截图翻译的全局热键 | `ctrl+alt+q` |
| 小窗透明度 | 结果小窗的不透明度 | `0.9` |
| 自动关闭 | 是否启用及多少秒后自动关闭结果小窗 | 启用 / 10 秒 |
| 网络超时 | API 请求超时时间 | 30 秒 |

### 推荐模型

需要具有视觉能力的大模型，推荐：

- **DeepSeek-v4.1-flash**
- **glm-5.3-flash**
- **kimi-k3**
- **GPT-4o 系列**（gpt-4o / gpt-4o-mini）

兼容任何 OpenAI 格式的 API 服务（OpenAI 官方、各类 OneAPI 中转站等），只需填写对应的 Base URL 和 API Key。

## 使用流程

```
按热键 Ctrl+Alt+Q
    ↓
全屏变暗 → 拖拽框选区域 / 点击选择窗口 / ESC 取消
    ↓
截图裁剪 → 发送给视觉大模型
    ↓
置顶小窗显示译文（可拖动、可自动关闭）
    ↓
下次按热键 → 自动翻译上次选中的区域/窗口
```

### 托盘菜单

| 菜单项 | 功能 |
|--------|------|
| 翻译 | 触发一次翻译（使用上次选择，或弹出选择界面） |
| 重新选择 | 强制弹出选择界面，重新选择区域或窗口 |
| 设置 | 打开设置界面 |
| 退出 | 退出程序 |

双击托盘图标也可触发翻译。

## 从源码构建 exe

```bash
uv pip install -r requirements.txt
uv run pyinstaller build.spec --noconfirm
# 输出 dist/闪译.exe
```

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 (Qt for Python) |
| 截图 | mss |
| 全局热键 | keyboard |
| HTTP 请求 | requests |
| 图像处理 | Pillow |
| 窗口操作 | Win32 API (ctypes) |
| 打包 | PyInstaller (--onefile --noconsole) |

## 项目结构

```
SnapTrans/
├── main.py              # 入口：流程编排、热键、托盘联动、首次引导
├── config.py            # 配置读写（config.json）+ 默认值 + 提示词
├── screen_capture.py    # mss 截图 + Win32 窗口工具
├── region_selector.py   # 全屏覆盖层（框选 + 窗口选择）
├── api_client.py        # OpenAI 兼容视觉 API 调用 + QThread Worker
├── result_window.py     # 置顶半透明结果小窗
├── settings_dialog.py   # 设置对话框
├── tray_icon.py         # 系统托盘图标 + 菜单
├── gen_icon.py          # 图标生成脚本
├── build.spec           # PyInstaller 打包配置
├── assets/icon.ico      # 应用图标
├── requirements.txt     # 依赖清单
└── LICENSE              # MIT License
```

## 已知限制

- **独占全屏 DirectX 游戏**：截图可能为黑屏，请将游戏切换为无边框窗口模式后使用
- **混合 DPI 多显示器**：框选坐标可能有微小偏差（单显示器和相同 DPI 多显示器完全正常）
- **部分游戏反作弊**：可能阻止全局热键钩子，以管理员身份运行可提高兼容性
- **打包体积**：单文件 exe 约 55MB（PySide6 固有体积）

## 许可证

[MIT License](LICENSE)
