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

### 打包程序

1. 安装 PyInstaller：
   ```bash
   pip install pyinstaller
   ```

2. 使用提供的配置文件打包：
   ```bash
   pyinstaller build.spec
   ```

打包完成后，可执行文件将生成在 `dist` 目录中。

## 使用说明

### Windows单文件exe版本使用方法

1. 从发布页面下载单文件版本 `default.exe`
2. 双击运行即可使用

> 注：单文件版本已包含所有必要组件，无需额外配置，开箱即用。

### AI分析功能配置

如需使用AI分析功能，需要配置智谱AI API密钥：

1. 访问[智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册/登录账号
3. 在控制台中[API keys 页面](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)创建新的API密钥
4. 将获取到的API密钥填入程序的"软件设置"页面

> 注：目前软件默认使用智谱AI的GLM-4V-Flash（免费的图像理解模型）。

## 技术栈

- Python
- Tkinter (GUI)
- FFmpeg (视频处理)
- ZhipuAI (AI 分析)

## 许可证

MIT License

## 作者

Aixiaozhen

## 版本历史

### v1.0.0 (2024-03-21)
- 初始发布版本
- 基础功能实现：
  - 视频场景自动检测
  - 关键帧提取和预览
  - AI内容安全分析
  - HTML风险报告生成
- 界面优化：
  - 自定义应用图标
  - 优化预览界面布局
  - 添加进度显示
- 技术改进：
  - 支持单文件打包发布
  - 集成FFmpeg
  - 使用智谱AI的GLM-4V-Flash模型

## 注意事项

- 请确保有足够的磁盘空间用于临时文件和报告生成
- 分析大型视频文件可能需要较长时间
- 确保系统已安装所需的运行时环境

## 问题反馈

如有问题或建议，请提交 Issue 或联系开发者。
