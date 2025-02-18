import tkinter as tk
from tkinter import ttk
import os
import subprocess
from tkinter import messagebox
from PIL import Image, ImageTk
import glob
import threading
import re
import queue
import base64
import requests
import json
from io import BytesIO
import time
from zhipuai import ZhipuAI
from abc import ABC, abstractmethod
from config_manager import ConfigManager
from tkinter import filedialog
from ai_analyzer import AIManager  # 从 ai_analyzer 导入 AIManager
import shutil
import webbrowser
from packaging import version
import sys
import socket
from img.logo import imgBase64


class VideoAnalyzer(tk.Tk):
    VERSION = "1.0.1"  # 当前版本号
    UPDATE_URL = "https://api.github.com/repos/aixiaozhen/Video_security_check/releases/latest"  # 替换为你的仓库地址
    
    def __init__(self):
        # 在创建窗口之前检查是否已经有实例在运行
        try:
            # 尝试绑定一个特定端口
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('localhost', 45678))  # 使用一个不常用的端口号
        except socket.error:
            messagebox.showerror("错误", "程序已经在运行！")
            sys.exit(1)
            
        super().__init__()

        # 设置窗口标题和尺寸
        self.title("视频安全检查工具")
        self.geometry("1024x700")
        self.resizable(False, False)
        
        # 设置窗口图标 - 使用绝对路径
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        # 创建和配置样式
        style = ttk.Style()
        # 无边框样式
        style.configure('Borderless.TFrame', borderwidth=0)
        style.configure('Borderless.TLabelframe', borderwidth=0)
        style.configure('Borderless.TLabelframe.Label', borderwidth=0)
        
        # 只保留外边框的样式
        style.configure('OuterBorder.TLabelframe', borderwidth=1, relief='solid')
        style.configure('OuterBorder.TLabelframe.Label', borderwidth=0)

        # 初始化配置管理器
        self.config_manager = ConfigManager()

        # 初始化分析相关的属性
        self.max_retries = 3
        self.retry_delay = 2
        self.concurrent_limit = 2
        self.request_semaphore = threading.Semaphore(self.concurrent_limit)
        self.analysis_results = {}
        self.pending_analysis = 0  # 添加待分析计数器
        self.auto_export_report = True  # 添加自动导出标志

        # 初始化 AI 管理器
        self.ai_manager = AIManager()
        self.available_models = self.ai_manager.get_available_analyzers()

        # 创建 UI 变量
        self.enable_ai = tk.BooleanVar(value=self.config_manager.config.get('enable_ai', False))
        self.current_model = tk.StringVar(value=self.config_manager.config.get('current_model', ''))
        self.sensitivity_value = tk.StringVar(value=str(self.config_manager.config.get('sensitivity', 0.2)))

        # 设置 ffmpeg 路径
        self.ffmpeg_path = self._get_ffmpeg_path()

        # 创建所有 UI 控件
        self._create_ui()
        
        # 加载保存的配置
        self._load_saved_config()

        # 注释掉自动检查更新
        # self.check_for_updates()

        # 在创建窗口后添加以下代码
        self.createTempLogo()
        self.wm_iconbitmap("temp.ico")  # 设置窗口图标
        if os.path.exists("temp.ico"):
            os.remove("temp.ico")  # 删除临时图标文件

    def _create_ui(self):
        # 创建主容器来组织所有内容 - 使用无边框样式
        main_container = ttk.Frame(self, style='Borderless.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)

        # 创建选项卡控件
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建第一个选项卡 - 视频处理
        video_tab = ttk.Frame(notebook, style='Borderless.TFrame')
        notebook.add(video_tab, text='视频处理')

        # 创建第二个选项卡 - 设置
        settings_tab = ttk.Frame(notebook, style='Borderless.TFrame')
        notebook.add(settings_tab, text='软件设置')

        # === 第一个选项卡的内容 ===
        # 文件选择区域
        self.file_frame = ttk.LabelFrame(video_tab, text="选择视频文件", style='Borderless.TLabelframe')
        self.file_frame.pack(padx=10, pady=10, fill=tk.X)

        # 创建左右分栏容器
        file_content_frame = ttk.Frame(self.file_frame)
        file_content_frame.pack(fill=tk.X, padx=5, pady=5)

        # 左侧视频信息区域
        info_frame = ttk.Frame(file_content_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 添加视频信息标签
        self.video_info = ttk.Label(
            info_frame, 
            text="等待选择视频文件...", 
            wraplength=600,
            justify=tk.LEFT,  # 文本左对齐
            anchor='w'  # 整体左对齐
        )
        self.video_info.pack(padx=5, pady=5, fill=tk.X)

        # 右侧按钮区域
        button_frame = ttk.Frame(file_content_frame)
        button_frame.pack(side=tk.RIGHT, padx=(10, 5))

        # 添加文件选择按钮
        self.select_button = ttk.Button(
            button_frame,
            text="选择视频文件",
            command=self.select_video_file,
            width=15  # 设置按钮宽度
        )
        self.select_button.pack(pady=(5, 2))  # 调整上下边距，与下面的按钮搭配

        # 添加风险报告按钮到文件选择按钮下方
        self.report_button = ttk.Button(
            button_frame,
            text="查看风险报告",
            command=self._show_risk_report,
            state='disabled',
            width=15  # 保持与上面按钮相同宽度
        )
        self.report_button.pack(pady=(2, 5))  # 调整上下边距

        # 预览区域
        self.preview_frame = ttk.LabelFrame(
            video_tab, 
            text="关键帧预览", 
            style='OuterBorder.TLabelframe'
        )
        self.preview_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # 创建画布和滚动条的容器
        self.canvas_container = ttk.Frame(self.preview_frame, style='OuterBorder.TFrame')
        self.canvas_container.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 创建画布
        self.canvas = tk.Canvas(
            self.canvas_container,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 创建垂直滚动条
        self.v_scrollbar = ttk.Scrollbar(
            self.canvas_container, 
            orient="vertical", 
            command=self.canvas.yview
        )
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置画布
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # 设置每行显示的列数和图片尺寸
        self.columns_per_row = 6   # 每行显示6列
        self.max_preview_width = 160  # 最大预览宽度
        self.current_row = 0
        self.current_col = 0

        # 分别存储文件路径和图片对象
        self.processed_files = []  # 存储已处理的文件路径
        self.preview_images = []   # 存储 PhotoImage 对象和对应的标签

        # 绑定画布大小变化事件
        self.canvas.bind('<Configure>', self.on_frame_configure)
        self.scrollable_frame.bind('<Configure>', self.on_frame_configure)

        # 底部状态栏区域
        status_frame = ttk.Frame(main_container)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 状态栏内部框架（用于固定高度）
        inner_status_frame = ttk.Frame(status_frame, height=30)
        inner_status_frame.pack(fill=tk.X, padx=10, pady=5)
        inner_status_frame.pack_propagate(False)  # 防止框架被内容压缩

        # 修改状态标签布局和显示方式
        self.status_frame = ttk.Frame(inner_status_frame)  # 创建一个新的框架来容纳状态标签和链接
        self.status_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="就绪",
            wraplength=0,  # 移除自动换行
            anchor='w',
            width=50  # 设置固定宽度
        )
        self.status_label.pack(side=tk.LEFT)
        
        # 添加打开链接标签（初始隐藏）
        self.open_link = ttk.Label(
            self.status_frame,
            text="打开",
            foreground="blue",
            cursor="hand2"  # 鼠标悬停时显示手型光标
        )
        # 初始不显示链接
        # self.open_link.pack(side=tk.LEFT, padx=(5, 0))
        
        # 绑定点击事件
        self.open_link.bind("<Button-1>", self._open_output_folder)

        # 进度条区域
        self.progress_frame = ttk.Frame(inner_status_frame)
        self.progress_frame.pack(side=tk.RIGHT)

        self.progress_label = ttk.Label(
            self.progress_frame, 
            text="",
            width=20
        )
        self.progress_label.pack(side=tk.LEFT, padx=(0, 5))

        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            mode='indeterminate',
            length=200
        )
        self.progress_bar.pack(side=tk.LEFT)

        # 创建队列用于线程间通信
        self.preview_queue = queue.Queue()

        # 绑定鼠标滚轮事件
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 绑定进入离开事件
        self.canvas.bind('<Enter>', lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind('<Leave>', lambda e: self.canvas.unbind_all("<MouseWheel>"))
        
        # 修改预览容器样式
        style = ttk.Style()
        style.configure("Risk.TFrame", background="red")
        style.configure("Safe.TFrame", background="green")

        # 在设置区域添加输出目录设置
        self.output_frame = ttk.LabelFrame(settings_tab, text="输出设置", style='Borderless.TLabelframe')
        self.output_frame.pack(padx=10, pady=10, fill=tk.X)

        # 使用视频目录的选项
        self.use_video_dir = tk.BooleanVar(value=self.config_manager.config.get('use_video_dir', True))
        self.use_video_dir_check = ttk.Checkbutton(
            self.output_frame,
            text="使用视频所在目录",
            variable=self.use_video_dir,
            command=self._toggle_output_dir
        )
        self.use_video_dir_check.pack(padx=5, pady=2, anchor='w')

        # 输出目录选择
        self.output_dir_frame = ttk.Frame(self.output_frame)
        self.output_dir_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(self.output_dir_frame, text="输出目录:").pack(side=tk.LEFT)
        
        self.output_dir_entry = ttk.Entry(self.output_dir_frame)
        self.output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.browse_button = ttk.Button(
            self.output_dir_frame,
            text="浏览...",
            command=self._browse_output_dir
        )
        self.browse_button.pack(side=tk.LEFT)

        # 加载保存的输出目录
        saved_dir = self.config_manager.config.get('output_dir', '')
        if saved_dir:
            self.output_dir_entry.insert(0, saved_dir)

        # === 第二个选项卡的内容 ===
        # AI设置区域
        self.ai_settings_frame = ttk.LabelFrame(settings_tab, text="AI 分析设置", style='Borderless.TLabelframe')
        self.ai_settings_frame.pack(padx=10, pady=10, fill=tk.X)

        # 启用AI分析的复选框
        self.ai_checkbox = ttk.Checkbutton(
            self.ai_settings_frame, 
            text="启用AI分析",
            variable=self.enable_ai,
            command=self._toggle_ai_settings
        )
        self.ai_checkbox.pack(padx=5, pady=5, anchor='w')

        # AI模型选择
        self.ai_model_frame = ttk.Frame(self.ai_settings_frame)
        self.ai_model_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(self.ai_model_frame, text="AI模型:").pack(side=tk.LEFT)

        # 获取可用的模型列表
        model_names = [model[1] for model in self.available_models]
        self.model_combobox = ttk.Combobox(
            self.ai_model_frame,
            textvariable=self.current_model,
            values=model_names,
            state='readonly',
            exportselection=0,
            justify='left'
        )
        if model_names:
            self.model_combobox.set(model_names[0])
        self.model_combobox.pack(side=tk.LEFT, padx=5)

        # API密钥设置
        self.api_key_frame = ttk.Frame(self.ai_settings_frame)
        self.api_key_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(self.api_key_frame, text="API密钥:").pack(side=tk.LEFT)

        self.api_key_entry = ttk.Entry(self.api_key_frame, state='disabled')
        self.api_key_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 设置初始 API 密钥值
        saved_api_key = self.config_manager.config.get('api_key', '')
        if saved_api_key:
            self.api_key_entry.config(state='normal')
            self.api_key_entry.delete(0, tk.END)
            self.api_key_entry.insert(0, saved_api_key)
            if not self.enable_ai.get():
                self.api_key_entry.config(state='disabled')

        # 添加 API 密钥输入框的变化监听
        self.api_key_entry.bind('<KeyRelease>', lambda e: self._save_config())
        self.api_key_entry.bind('<FocusOut>', lambda e: self._save_config())

        # 创建按钮容器框架
        button_frame = ttk.Frame(self.ai_settings_frame)
        button_frame.pack(padx=5, pady=5, fill=tk.X)

        # 只保留配置文件目录按钮
        self.config_button = ttk.Button(
            button_frame,
            text="打开配置目录",
            command=self._open_config_dir
        )
        self.config_button.pack(side=tk.LEFT, padx=5)

        # 场景检测设置区域
        self.detection_frame = ttk.LabelFrame(settings_tab, text="场景检测设置", style='Borderless.TLabelframe')
        self.detection_frame.pack(padx=10, pady=10, fill=tk.X)

        # 创建场景检测灵敏度滑动条
        self.sensitivity_frame = ttk.Frame(self.detection_frame)
        self.sensitivity_frame.pack(padx=5, pady=5, fill=tk.X)

        ttk.Label(self.sensitivity_frame, text="场景检测灵敏度:").pack(side=tk.LEFT, padx=5)

        # 先创建标签
        self.sensitivity_label = ttk.Label(self.sensitivity_frame, text="0.2")
        self.sensitivity_label.pack(side=tk.RIGHT, padx=5)

        # 然后创建滑动条
        self.sensitivity_scale = ttk.Scale(
            self.sensitivity_frame,
            from_=0.1,
            to=0.9,
            orient=tk.HORIZONTAL,
            command=self.update_sensitivity_label
        )
        self.sensitivity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.sensitivity_scale.set(0.2)
        self.update_sensitivity_label(0.2)

        # 最后再设置输出目录状态
        self._toggle_output_dir()

        # 修改帮助菜单
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="检查更新", command=self.check_for_updates)
        help_menu.add_separator()  # 添加分隔线
        help_menu.add_command(label="关于", command=self._show_about)

    def _load_saved_config(self):
        """加载保存的配置"""
        config = self.config_manager.config
        
        # 设置 AI 启用状态
        self.enable_ai.set(config.get('enable_ai', False))
        
        # 设置模型
        if config.get('current_model'):
            self.current_model.set(config['current_model'])
            try:
                model_key = next(key for key, name in self.available_models 
                               if name == self.current_model.get())
                # 如果启用了 AI 且有 API 密钥，配置分析器
                if self.enable_ai.get() and config.get('api_key'):
                    self.ai_manager.configure_analyzer(model_key, config['api_key'])
                    self.ai_manager.set_current_analyzer(model_key)
            except StopIteration:
                print("Warning: Saved model not found in available models")
                if self.available_models:  # 如果有可用模型，使用第一个
                    self.current_model.set(self.available_models[0][1])
        elif self.available_models:  # 如果没有保存的模型但有可用模型，使用第一个
            self.current_model.set(self.available_models[0][1])
        
        # 设置灵敏度
        if 'sensitivity' in config:
            self.sensitivity_scale.set(config['sensitivity'])
        
        # 更新 UI 状态
        self._toggle_ai_settings()

    def _save_config(self):
        """保存当前配置"""
        # 检查必要的控件是否已创建
        if not hasattr(self, 'api_key_entry') or not hasattr(self, 'output_dir_entry'):
            return

        config = {
            'enable_ai': self.enable_ai.get(),
            'current_model': self.current_model.get(),
            'api_key': self.api_key_entry.get().strip(),
            'sensitivity': float(self.sensitivity_scale.get()),
            'output_dir': self.output_dir_entry.get().strip(),
            'use_video_dir': self.use_video_dir.get()
        }
        print("Saving config:", config)  # 添加调试输出
        self.config_manager.save_config(config)

    def _toggle_ai_settings(self):
        """切换AI设置的启用状态"""
        # 修改状态设置逻辑
        combobox_state = 'readonly' if self.enable_ai.get() else 'disabled'  # combobox状态
        entry_state = 'normal' if self.enable_ai.get() else 'disabled'  # entry状态
        
        self.model_combobox.config(state=combobox_state)  # combobox使用readonly/disabled
        self.api_key_entry.config(state=entry_state)  # entry使用normal/disabled
        
        # 如果禁用了 AI，清除当前分析器
        if not self.enable_ai.get():
            self.ai_manager.current_analyzer = None
        # 如果启用了 AI，且有选择模型和 API 密钥，则配置分析器
        elif self.current_model.get() and self.api_key_entry.get().strip():
            try:
                model_key = next(key for key, name in self.available_models 
                               if name == self.current_model.get())
                self.ai_manager.configure_analyzer(model_key, self.api_key_entry.get().strip())
                self.ai_manager.set_current_analyzer(model_key)
            except StopIteration:
                pass
        
        # 保存配置
        self._save_config()

    def _open_config_dir(self):
        """打开配置文件所在目录"""
        config_dir = self.config_manager.get_config_dir()
        if os.path.exists(config_dir):
            os.startfile(config_dir)  # Windows
            # 对于其他操作系统：
            # import subprocess
            # subprocess.run(['open', config_dir])  # macOS
            # subprocess.run(['xdg-open', config_dir])  # Linux

    def select_video_file(self):
        """打开文件选择对话框选择视频文件"""
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            # 验证文件格式
            if not file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                messagebox.showerror("错误", "请选择有效的视频文件！")
                return
            
            # 更新视频信息显示
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            self.video_info.config(
                text=f"当前视频：{file_name}\n"
                     f"完整路径：{file_path}\n"
                     f"文件大小：{file_size:.2f} MB"
            )
            
            # 检查AI设置
            if self.enable_ai.get():
                if not self.current_model.get():
                    messagebox.showerror("错误", "请选择AI模型！")
                    return
                if not self.api_key_entry.get():
                    messagebox.showerror("错误", "请输入API密钥！")
                    return
                
                try:
                    # 配置AI分析器并保存配置
                    model_key = next(key for key, name in self.available_models 
                                   if name == self.current_model.get())
                    self.ai_manager.configure_analyzer(model_key, self.api_key_entry.get())
                    self.ai_manager.set_current_analyzer(model_key)
                    self._save_config()
                except StopIteration:
                    messagebox.showerror("错误", "无效的AI模型选择！")
                    return
            
            self.process_video(file_path)

    def update_sensitivity_label(self, value):
        """更新灵敏度标签显示"""
        try:
            # 将值转换为浮点数并四舍五入到最近的0.1
            value = float(value)
            rounded_value = round(value * 10) / 10
            
            # 更新标签和变量
            self.sensitivity_label.config(text=f"{rounded_value:.1f}")
            self.sensitivity_value.set(str(rounded_value))
            
            # 如果值不等于四舍五入后的值，更新滑动条位置
            if abs(float(value) - rounded_value) > 0.001:  # 使用小数点比较
                self.sensitivity_scale.set(rounded_value)
            
            # 保存配置
            self._save_config()
        except ValueError:
            print(f"Invalid value: {value}")

    def process_video(self, video_path):
        # 检查 ffmpeg 是否可用
        ffmpeg_path = self._get_ffmpeg_path()
        if not ffmpeg_path:
            return
        
        # 修改 ffmpeg 命令调用，使用完整路径
        command = [
            ffmpeg_path,  # 使用完整路径
            '-i', video_path,
            '-vf', f"select='gt(scene,{self.sensitivity_value.get()})'",
            '-vsync', 'vfr',
            '-q:v', '2',
            os.path.join(os.path.dirname(video_path), 'temp_%04d.jpg')
        ]

        self.status_label.config(text="正在处理视频，请稍候...")
        self.progress_label.config(text="准备处理...")
        self.progress_bar.start(10)  # 启动进度条动画
        
        # 隐藏打开链接
        self.open_link.pack_forget()
        
        # 清理预览区域和分析结果
        for _, container in self.preview_images:
            container.destroy()
        self.preview_images.clear()
        self.processed_files.clear()
        self.analysis_results.clear()  # 清除旧的分析结果
        
        # 禁用风险报告按钮
        self.report_button.config(state='disabled')

        # 重置行列计数
        self.current_row = 0
        self.current_col = 0

        # 创建处理线程
        thread = threading.Thread(
            target=self._process_video_thread,
            args=(video_path,),
            daemon=True
        )
        thread.start()

        # 启动预览更新检查
        self.after(100, self._check_preview_queue)

    def _process_video_thread(self, video_path):
        try:
            ffmpeg_path = self._get_ffmpeg_path()
            print(f"Using ffmpeg path: {ffmpeg_path}")  # 调试输出
            print(f"ffmpeg exists: {os.path.exists(ffmpeg_path)}")  # 检查文件是否存在
            
            # 获取视频文件名（不含扩展名）和时间戳
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # 创建输出目录名称（只包含视频名和时间戳）
            frames_dir_name = f"{video_name}_{timestamp}"
            # 清理目录名中的非法字符
            frames_dir_name = re.sub(r'[<>:"/\\|?*]', '_', frames_dir_name)
            
            # 根据设置选择基础目录
            if self.use_video_dir.get():
                # 使用视频所在目录
                base_dir = os.path.dirname(os.path.abspath(video_path))
            else:
                # 使用自定义目录，如果未设置则默认使用视频所在目录
                custom_dir = self.output_dir_entry.get().strip()
                base_dir = custom_dir if custom_dir else os.path.dirname(os.path.abspath(video_path))
            
            # 组合完整的输出路径
            frames_dir = os.path.join(base_dir, frames_dir_name)
            
            # 创建目录
            if not os.path.exists(frames_dir):
                os.makedirs(frames_dir)

            # 更新状态显示（只显示目录名，不显示完整路径）
            self.preview_queue.put(('update_status', f"正在处理: {frames_dir_name}"))

            # 获取当前灵敏度值
            sensitivity = self.sensitivity_value.get()
            
            # 使用ffmpeg提取关键帧
            temp_pattern = os.path.join(frames_dir, 'temp_%04d.jpg').replace('\\', '/')
            
            # 使用完整的 ffmpeg 路径
            ffmpeg_path = self._get_ffmpeg_path()
            
            # 修改提取命令
            extract_command = [
                ffmpeg_path,  # 使用完整路径而不是 'ffmpeg'
                '-i', video_path,
                '-vf', f"select='gt(scene,{sensitivity})'",
                '-vsync', 'vfr',
                '-q:v', '2',
                temp_pattern
            ]

            print(f"Running command: {' '.join(extract_command)}")  # 打印完整命令
            
            # 执行提取命令
            process = subprocess.Popen(
                extract_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace',
                creationflags=0x08000000  # Windows下隐藏控制台窗口
            )

            # 读取输出并更新进度
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                # 检查是否生成了新的图片
                frame_files = sorted(glob.glob(os.path.join(frames_dir, 'temp_*.jpg')))
                for frame_file in frame_files:
                    if frame_file not in self.processed_files:
                        # 获取帧号
                        frame_num = int(os.path.basename(frame_file).replace('temp_', '').replace('.jpg', ''))
                        
                        try:
                            # 计算大致时间戳（这是一个估算）
                            fps = 25  # 假设视频是25帧每秒
                            timestamp = frame_num / fps
                            
                            # 格式化时间戳
                            hours = int(timestamp // 3600)
                            minutes = int((timestamp % 3600) // 60)
                            seconds = int(timestamp % 60)
                            milliseconds = int((timestamp % 1) * 1000)
                            
                            # 创建新的文件名，去掉 "frame_" 前缀
                            new_filename = f'{hours:02d}-{minutes:02d}-{seconds:02d}.{milliseconds:03d}.jpg'
                            new_filepath = os.path.join(frames_dir, new_filename)
                            
                            # 重命名文件
                            os.rename(frame_file, new_filepath)
                            
                            # 添加到预览队列
                            self.preview_queue.put(('add_preview', new_filepath))
                            self.processed_files.append(new_filepath)
                        except Exception as e:
                            print(f"Error processing frame {frame_file}: {e}")

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, extract_command)

            # 处理完成
            self.preview_queue.put(('complete', None))

        except Exception as e:
            self.preview_queue.put(('error', str(e)))

    def _check_preview_queue(self):
        try:
            while True:
                action, data = self.preview_queue.get_nowait()
                
                if action == 'add_preview':
                    self._add_preview_image(data)
                    self.progress_label.config(text=f"已提取 {len(self.processed_files)} 个关键帧")
                elif action == 'update_status':
                    self.status_label.config(text=data)
                elif action == 'complete':
                    self.progress_bar.stop()
                    
                    # 获取输出目录
                    if self.processed_files:
                        output_dir = os.path.dirname(self.processed_files[0])
                        # 更新状态栏显示完整信息
                        self.status_label.config(
                            text=f"处理完成 - 共提取 {len(self.processed_files)} 个关键帧 - 保存位置：{output_dir}"
                        )
                        self.progress_label.config(text="完成！")
                        
                        # 如果启用了AI分析且有风险项，启用风险报告按钮
                        if self.enable_ai.get() and any(
                            not result.get('is_safe', True) 
                            for result in self.analysis_results.values()
                        ):
                            self.report_button.config(state='normal')
                        else:
                            self.report_button.config(state='disabled')
                    return
                elif action == 'error':
                    self.progress_bar.stop()
                    self.progress_label.config(text="处理失败")
                    self.status_label.config(text=f"处理失败 - {data}")
                    messagebox.showerror("错误", f"视频处理失败！\n错误信息：{data}")
                    return

        except queue.Empty:
            # 继续检查队列
            self.after(100, self._check_preview_queue)

    def _add_preview_image(self, image_path):
        try:
            # 打开图片
            img = Image.open(image_path)
            
            # 计算等比例缩放尺寸，以宽度为基准
            width, height = img.size
            ratio = self.max_preview_width / width
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            # 调整图片大小
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            # 从文件名中提取时间码（去掉了 frame_ 前缀的处理）
            time_str = os.path.basename(image_path).replace('.jpg', '')
            
            # 创建预览容器
            preview_container = ttk.Frame(self.scrollable_frame)
            preview_container.grid(row=self.current_row, column=self.current_col, padx=5, pady=5, sticky='nsew')
            
            # 创建图片标签
            image_label = ttk.Label(preview_container, image=photo)
            image_label.pack(pady=(0, 2))
            
            # 创建时间码标签
            time_label = ttk.Label(preview_container, text=time_str)
            time_label.pack()

            # 创建分析状态标签
            analysis_label = ttk.Label(preview_container, text="")
            analysis_label.pack()

            # 保存引用
            self.preview_images.append((photo, preview_container))

            # 只在启用 AI 分析且正确配置了分析器时才启动分析线程
            if (self.enable_ai.get() and 
                self.ai_manager.current_analyzer and 
                self.ai_manager.current_analyzer.is_configured()):
                analysis_label.config(text="正在分析...")
                self.pending_analysis += 1  # 增加待分析计数
                analysis_thread = threading.Thread(
                    target=self._analyze_image_thread,
                    args=(image_path, preview_container, analysis_label),
                    daemon=True
                )
                analysis_thread.start()

            # 更新行列位置
            self.current_col += 1
            if self.current_col >= self.columns_per_row:
                self.current_col = 0
                self.current_row += 1

            # 配置网格列的权重，使其均匀分布
            for i in range(self.columns_per_row):
                self.scrollable_frame.grid_columnconfigure(i, weight=1)

            # 更新画布滚动区域
            self.scrollable_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # 自动滚动到最新的图片
            self.canvas.yview_moveto(1.0)
            
            # 强制更新显示
            self.update_idletasks()
        except Exception as e:
            print(f"Error adding preview: {e}")
            messagebox.showerror("错误", f"添加预览图片失败：{str(e)}")

    def _analyze_image_thread(self, image_path, container, label):
        try:
            # 使用 AI 管理器进行分析
            response = self.ai_manager.analyze_image(image_path)
            result = self.ai_manager.current_analyzer.parse_response(response)
            
            # 更新界面
            self.after(0, lambda: self._update_analysis_result(
                container, label, 
                result['is_safe'], 
                result['risk_type'], 
                result['description']
            ))
            
            # 存储结果
            self.analysis_results[image_path] = result
            
            # 更新待分析计数并检查是否所有分析都完成
            self.pending_analysis -= 1
            if self.pending_analysis == 0:
                # 如果有风险项，自动导出报告
                has_risks = any(not result.get('is_safe', True) 
                              for result in self.analysis_results.values())
                
                if has_risks and self.auto_export_report:
                    self.after(0, self._auto_export_report)

        except Exception as e:
            error_msg = str(e)
            print(f"Error in analysis thread for {image_path}: {e}")
            
            # 处理欠费错误
            if "账户已欠费" in error_msg:
                self.after(0, lambda: [
                    label.config(text="AI服务已欠费", foreground="red"),
                    messagebox.showerror("错误", "AI服务账户已欠费，请充值后重试"),
                    # 禁用 AI 分析功能
                    self.enable_ai.set(False),
                    self._toggle_ai_settings()
                ])
            else:
                # 其他错误的处理
                self.after(0, lambda: label.config(
                    text="分析出错", 
                    foreground="red"
                ))
            self.pending_analysis -= 1  # 确保在出错时也减少计数

    def _update_analysis_result(self, container, label, is_safe, risk_type, description):
        try:
            if is_safe:
                # 移除背景色设置，只使用文字颜色
                label.config(
                    text="安全",
                    foreground="green")
            else:
                # 移除背景色设置，只使用文字颜色
                label.config(
                    text=f"风险: {risk_type}" if risk_type else "风险",
                    foreground="red")
            
            # 添加提示信息
            label.bind('<Enter>', lambda e: self._show_tooltip(e, description))
            label.bind('<Leave>', lambda e: self._hide_tooltip())
            
            print(f"Updated UI - is_safe: {is_safe}, risk_type: {risk_type}")  # 调试输出
        except Exception as e:
            print(f"Error updating UI: {e}")

    def _show_tooltip(self, event, text):
        x, y, _, _ = event.widget.bbox("insert")
        x += event.widget.winfo_rootx() + 25
        y += event.widget.winfo_rooty() + 20

        # 创建工具提示窗口
        self.tooltip = tk.Toplevel()
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")

        label = ttk.Label(self.tooltip, text=text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1)
        label.pack()

    def _hide_tooltip(self):
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()

    def on_frame_configure(self, event=None):
        # 确保滚动区域覆盖所有内容
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # 设置固定宽度，考虑到边距和滚动条
        width = self.preview_frame.winfo_width() - 25  # 减去边距和滚动条宽度
        self.canvas.itemconfig(self.canvas_frame, width=width)
        
        # 重新配置所有列的权重
        for i in range(self.columns_per_row):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

    def _on_mousewheel(self, event):
        # 调整垂直滚动
        self.canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")

    def _toggle_output_dir(self):
        """切换输出目录设置的启用状态"""
        state = 'disabled' if self.use_video_dir.get() else 'normal'
        self.output_dir_entry.config(state=state)
        self.browse_button.config(state=state)
        self._save_config()

    def _browse_output_dir(self):
        """浏览并选择输出目录"""
        directory = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=self.output_dir_entry.get() or os.path.expanduser("~")
        )
        if directory:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, directory)
            self._save_config()

    def _show_risk_report(self):
        """显示风险报告窗口"""
        # 创建报告窗口
        report_window = tk.Toplevel(self)
        report_window.title("风险分析报告")
        report_window.geometry("800x600")
        report_window.resizable(False, False)  # 禁止调整窗口大小
        
        # 设置子窗口图标
        self.createTempLogo()
        report_window.iconbitmap("temp.ico")  # 设置窗口图标
        if os.path.exists("temp.ico"):
            os.remove("temp.ico")  # 删除临时图标文件

        # 创建报告内容
        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加标题
        title_label = ttk.Label(
            report_frame, 
            text="风险分析报告", 
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=10)
        
        # 创建左右分栏的容器
        content_frame = ttk.Frame(report_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 左侧列表区域
        list_frame = ttk.Frame(content_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 创建风险列表（使用Treeview实现表格效果）
        columns = ('时间点', '风险类型', '详细说明')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        # 设置列标题和宽度
        tree.heading('时间点', text='时间点')
        tree.heading('风险类型', text='风险类型')
        tree.heading('详细说明', text='详细说明')
        
        tree.column('时间点', width=100)
        tree.column('风险类型', width=100)
        tree.column('详细说明', width=200)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # 放置树形视图和滚动条
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 右侧预览区域
        preview_frame = ttk.LabelFrame(content_frame, text="图片预览")
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 预览内容容器
        preview_content = ttk.Frame(preview_frame)
        preview_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 用于显示选中图片的标签
        preview_label = ttk.Label(preview_content)
        preview_label.pack(pady=5)
        
        # 修改风险详情标签的显示方式
        detail_label = ttk.Label(
            preview_content, 
            wraplength=300,  # 调整文字换行宽度
            justify='left',  # 文字左对齐
            anchor='w'  # 整体左对齐
        )
        detail_label.pack(fill=tk.X, pady=5)
        
        # 填充风险数据
        risk_items = []
        for image_path, result in self.analysis_results.items():
            if not result.get('is_safe', True):
                # 从文件名提取时间点
                time_str = os.path.basename(image_path).replace('.jpg', '')
                risk_items.append({
                    'time': time_str,
                    'path': image_path,
                    'risk_type': result.get('risk_type', '未知风险'),
                    'description': result.get('description', '无详细说明')
                })
        
        # 按时间排序
        risk_items.sort(key=lambda x: x['time'])
        
        # 添加到树形视图
        for item in risk_items:
            tree.insert('', tk.END, values=(
                item['time'],
                item['risk_type'],
                item['description']
            ), tags=(item['path'],))
        
        # 修改选择事件处理
        def on_select(event):
            selected = tree.selection()
            if selected:
                item = tree.item(selected[0])
                path = tree.item(selected[0])['tags'][0]
                
                # 显示图片
                img = Image.open(path)
                # 调整图片大小
                img.thumbnail((400, 300))
                photo = ImageTk.PhotoImage(img)
                preview_label.configure(image=photo)
                preview_label.image = photo  # 保持引用
                
                # 显示详细信息
                result = self.analysis_results[path]
                detail_text = f"风险类型：{result['risk_type']}\n\n详细说明：{result['description']}"
                detail_label.configure(text=detail_text)
                
                # 确保标签完全展示
                preview_frame.update_idletasks()
        
        tree.bind('<<TreeviewSelect>>', on_select)

    def _auto_export_report(self):
        """自动导出风险报告"""
        try:
            # 获取第一个处理过的文件所在目录作为基准目录
            if not self.processed_files:
                print("错误：没有可用的图片数据")
                return
            
            base_dir = os.path.dirname(self.processed_files[0])
            
            # 使用固定的报告文件名
            file_path = os.path.join(base_dir, "安全分析报告.html")
            report_dir = os.path.join(base_dir, "report_files")
            
            # 创建报告目录（如果已存在则先删除）
            if os.path.exists(report_dir):
                shutil.rmtree(report_dir)
            os.makedirs(report_dir)
            
            # 复制风险图片到报告目录并收集风险项
            risk_items = []
            for image_path, result in self.analysis_results.items():
                if not result.get('is_safe', True):
                    # 复制图片
                    new_image_path = os.path.join(report_dir, os.path.basename(image_path))
                    shutil.copy2(image_path, new_image_path)
                    
                    risk_items.append({
                        'time': os.path.basename(image_path).replace('.jpg', ''),
                        'image': os.path.basename(image_path),
                        'risk_type': result.get('risk_type', '未知风险'),
                        'description': result.get('description', '无详细说明')
                    })
            
            # 如果没有风险项，不生成报告
            if not risk_items:
                return

            # 生成HTML报告
            html_content = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family:Arial,sans-serif;margin:20px; }}
                    h1 {{ text-align:center; color:#333; }}
                    p {{ text-align:center; color:#666; }}
                    .risk-list {{ display:flex; flex-wrap:wrap; justify-content:flex-start; }}
                    .risk-item {{ width:calc(16.666% - 20px);margin-bottom:30px;border:1px solid #ccc;border-radius:5px;padding:10px;box-sizing:border-box;box-shadow:0 2px 4px rgba(0,0,0,0.1);margin-right:20px; }}
                    .risk-item:nth-child(6n) {{ margin-right:0; }}
                    .risk-image {{ max-width:100%; height:auto; display:block; margin:0 auto; }}
                    .risk-info {{ margin-top: 10px; }}
                    .risk-type {{ color: red; font-weight: bold; }}
                </style>
            </head>
            <body>
                <h1>视频安全分析风险报告</h1>
                <p>生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <div class="risk-list">
            """
            
            for item in sorted(risk_items, key=lambda x: x['time']):
                html_content += f"""
                    <div class="risk-item">
                        <h3>时间点：{item['time']}</h3>
                        <img class="risk-image" src="{os.path.basename(report_dir)}/{item['image']}">
                        <div class="risk-info">
                            <p class="risk-type">风险类型：{item['risk_type']}</p>
                            <p>详细说明：{item['description']}</p>
                        </div>
                    </div>
                """
            
            html_content += """
                </div>
            </body>
            </html>
            """
            
            # 保存HTML文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # 保存当前输出目录路径
            self.current_output_dir = base_dir
            
            # 更新状态栏显示并显示打开链接
            self.status_label.config(text=f"风险报告已自动导出：{os.path.basename(file_path)}")
            
            # 显示打开链接
            self.open_link.pack(side=tk.LEFT, padx=(5, 0))
            
            # 确保所有风险项都已处理完成后再启用按钮
            if self.pending_analysis == 0:
                self.report_button.config(state='normal')
            
        except Exception as e:
            print(f"自动导出报告失败：{str(e)}")
            self.status_label.config(text=f"自动导出报告失败：{str(e)}")
            # 发生错误时隐藏打开链接
            self.open_link.pack_forget()

    def _open_output_folder(self, event=None):
        """打开输出文件夹"""
        if hasattr(self, 'current_output_dir') and os.path.exists(self.current_output_dir):
            os.startfile(self.current_output_dir)  # Windows
            # 对于其他操作系统：
            # import subprocess
            # subprocess.run(['open', self.current_output_dir])  # macOS
            # subprocess.run(['xdg-open', self.current_output_dir])  # Linux

    def _get_ffmpeg_path(self):
        """获取 ffmpeg 可执行文件路径"""
        try:
            # 如果是打包后的程序，优先使用打包的 ffmpeg
            if getattr(sys, 'frozen', False):
                if hasattr(sys, '_MEIPASS'):
                    # PyInstaller 打包环境
                    bundled_ffmpeg = os.path.join(sys._MEIPASS, 'bin', 'ffmpeg.exe')
                else:
                    # 其他打包环境
                    bundled_ffmpeg = os.path.join(os.path.dirname(sys.executable), 'bin', 'ffmpeg.exe')
            else:
                # 开发环境
                bundled_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'ffmpeg.exe')
            
            if os.path.exists(bundled_ffmpeg):
                return bundled_ffmpeg
            
            # 如果找不到打包的 ffmpeg，尝试系统路径（这部分代码可以保留但不会被使用）
            if os.name == 'nt':
                result = subprocess.run(['where', 'ffmpeg'], 
                                     capture_output=True, 
                                     text=True)
                if result.returncode == 0:
                    return 'ffmpeg'
            else:
                result = subprocess.run(['which', 'ffmpeg'], 
                                     capture_output=True, 
                                     text=True)
                if result.returncode == 0:
                    return 'ffmpeg'
                
        except Exception as e:
            print(f"Error finding ffmpeg: {e}")
        
        # 如果找不到 ffmpeg，显示错误消息并退出程序
        messagebox.showerror(
            "错误",
            "找不到 ffmpeg。程序无法继续运行，请确保程序完整性或联系技术支持。"
        )
        sys.exit(1)  # 直接退出程序

    def check_for_updates(self):
        """检查软件更新"""
        try:
            # 添加超时和代理处理
            proxies = {
                'http': None,
                'https': None
            }
            
            response = requests.get(
                self.UPDATE_URL, 
                timeout=5,
                proxies=proxies,  # 禁用代理
                verify=False      # 禁用 SSL 验证
            )
            
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release['tag_name'].lstrip('v')
                
                if version.parse(latest_version) > version.parse(self.VERSION):
                    # 有新版本可用
                    result = messagebox.askyesno(
                        "发现新版本",
                        f"当前版本：{self.VERSION}\n"
                        f"最新版本：{latest_version}\n\n"
                        f"更新内容：\n{latest_release['body']}\n\n"
                        "是否前往下载页面？"
                    )
                    
                    if result:
                        webbrowser.open(latest_release['html_url'])
                else:
                    messagebox.showinfo(
                        "检查更新",
                        "当前已是最新版本。"
                    )
        except requests.exceptions.RequestException as e:
            # 静默处理网络错误，不显示错误消息框
            print(f"检查更新失败: {str(e)}")
        except Exception as e:
            # 其他错误才显示错误消息框
            messagebox.showerror(
                "检查更新失败",
                f"无法检查更新：{str(e)}\n"
                "请检查网络连接后重试。"
            )

    def _show_about(self):
        """显示关于对话框"""
        about_window = tk.Toplevel(self)
        about_window.title("关于")
        about_window.geometry("400x300")
        about_window.resizable(False, False)
        
        # 设置子窗口图标
        self.createTempLogo()
        about_window.iconbitmap("temp.ico")  # 设置窗口图标
        if os.path.exists("temp.ico"):
            os.remove("temp.ico")  # 删除临时图标文件
        
        # 设置模态对话框
        about_window.transient(self)
        about_window.grab_set()
        
        # 创建内容框架
        content_frame = ttk.Frame(about_window)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 添加软件名称
        title_label = ttk.Label(
            content_frame,
            text="视频安全检查工具",
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 10))
        
        # 添加版本信息
        version_label = ttk.Label(
            content_frame,
            text=f"版本 {self.VERSION}",
            font=('Arial', 10)
        )
        version_label.pack(pady=(0, 10))
        
        # 添加软件说明
        description = """
        本工具用于辅助内容审核，对视频快速安全检查：
        • 使用FFmpeg自动检测场景并生成截图
        • 使用AI大模型对关键帧截图智能分析
        • 生成并导出风险报告
        """
        desc_label = ttk.Label(
            content_frame,
            text=description,
            justify=tk.LEFT,
            wraplength=350
        )
        desc_label.pack(pady=(0, 10))
        
        # 添加版权信息
        copyright_label = ttk.Label(
            content_frame,
            text="Copyright © Aixiaozhen 2025",
            font=('Arial', 9)
        )
        copyright_label.pack(pady=(0, 10))
        
        # 添加确定按钮
        ttk.Button(
            content_frame,
            text="确定",
            command=about_window.destroy,
            width=15
        ).pack(pady=(10, 0))
        
        # 设置对话框位置为屏幕中心
        about_window.update_idletasks()
        width = about_window.winfo_width()
        height = about_window.winfo_height()
        x = (about_window.winfo_screenwidth() // 2) - (width // 2)
        y = (about_window.winfo_screenheight() // 2) - (height // 2)
        about_window.geometry(f'+{x}+{y}')

    def destroy(self):
        # 关闭程序时释放socket
        if hasattr(self, 'socket'):
            self.socket.close()
        super().destroy()

    def createTempLogo(self):
        tmp = open("temp.ico", "wb+")  # 创建temp.ico临时文件
        tmp.write(base64.b64decode(imgBase64))  # 写入img的base64
        tmp.close()


if __name__ == '__main__':
    app = VideoAnalyzer()
    app.mainloop()
