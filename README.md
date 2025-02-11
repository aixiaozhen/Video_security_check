# 视频安全检查工具 (Video Security Check Tool)

一个用于自动检测和分析视频内容安全风险的桌面应用程序。

## 功能特点

- 视频内容自动分析
- 智能识别潜在风险内容
- 自动生成风险报告
- 支持批量处理视频文件
- 可视化界面操作
- HTML格式报告导出

## 系统要求

- Windows 操作系统
- Python 3.11 或更高版本
- FFmpeg (已包含在发布版本中)

## 安装说明

1. 从 Releases 页面下载最新版本的可执行文件
2. 解压下载的文件到任意目录
3. 运行 `视频安全检查工具.exe`

## 开发环境搭建

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/video-security-check.git
   cd video-security-check
   ```

2. 创建并激活虚拟环境：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 下载 FFmpeg：
   - 下载 FFmpeg 可执行文件
   - 将 ffmpeg.exe 放置在 `bin` 目录下

## 使用说明

1. 启动程序
2. 选择要分析的视频文件
3. 点击"开始分析"按钮
4. 等待分析完成
5. 查看生成的安全风险报告

## 技术栈

- Python
- Tkinter (GUI)
- FFmpeg (视频处理)
- ZhipuAI (AI 分析)

## 许可证

MIT License

## 作者

[Aixiaozhen]

## 版本历史

- v1.0.0 - 初始发布版本

## 注意事项

- 请确保有足够的磁盘空间用于临时文件和报告生成
- 分析大型视频文件可能需要较长时间
- 确保系统已安装所需的运行时环境

## 问题反馈

如有问题或建议，请提交 Issue 或联系开发者。
