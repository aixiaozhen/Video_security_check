import tkinter as tk
from tkinter import ttk
import os
import subprocess
from tkinter import messagebox
from PIL import Image, ImageTk
import glob
from tkinterdnd2 import DND_FILES, TkinterDnD
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


class AIAnalyzer(ABC):
    """AI分析器的抽象基类"""
    
    @abstractmethod
    def analyze_image(self, image_path):
        """分析图片的抽象方法"""
        pass

    @abstractmethod
    def get_name(self):
        """获取分析器名称"""
        pass

    @abstractmethod
    def is_configured(self):
        """检查是否配置完成"""
        pass

class ZhipuAnalyzer(AIAnalyzer):
    """智谱AI分析器"""
    
    def __init__(self):
        self.api_key = ""
        self.client = None
        self.max_retries = 3
        self.retry_delay = 2

    def configure(self, api_key):
        """配置API密钥"""
        self.api_key = api_key
        self.client = ZhipuAI(api_key=api_key)
        
    def get_name(self):
        return "智谱 GLM-4V"
        
    def is_configured(self):
        return bool(self.api_key and self.client)

    def analyze_image(self, image_path):
        if not self.is_configured():
            raise ValueError("API key not configured")

        for attempt in range(self.max_retries):
            try:
                with open(image_path, 'rb') as image_file:
                    img_base = base64.b64encode(image_file.read()).decode('utf-8')

                response = self.client.chat.completions.create(
                    model="glm-4v-plus",
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": img_base}
                            },
                            {
                                "type": "text",
                                "text": "请以少儿内容专家的身份，分析这张图片是否安全是否适合儿童观看，主要关注：暴力、恐怖、政治、地球、地图等不适内容。请用JSON格式回复：{is_safe: true/false, risk_type: 风险类型, description: 说明}"
                            }
                        ]
                    }]
                )
                return response

            except Exception as e:
                error_str = str(e)
                if "429" in error_str:
                    print(f"并发限制错误，等待重试: {e}")
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                elif "400" in error_str:
                    return {
                        "choices": [{
                            "message": {
                                "content": json.dumps({
                                    "is_safe": False,
                                    "risk_type": "敏感内容",
                                    "description": "系统检测到可能的敏感内容"
                                })
                            }
                        }]
                    }
                else:
                    print(f"其他错误 (尝试 {attempt + 1}): {e}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                    else:
                        raise

        return None

class AIManager:
    """AI分析器管理类"""
    
    def __init__(self):
        self.analyzers = {
            "zhipu": ZhipuAnalyzer(),
            # 在这里添加其他AI分析器
        }
        self.current_analyzer = None

    def get_available_analyzers(self):
        """获取所有可用的分析器"""
        return [(key, analyzer.get_name()) for key, analyzer in self.analyzers.items()]

    def set_current_analyzer(self, analyzer_key):
        """设置当前使用的分析器"""
        if analyzer_key in self.analyzers:
            self.current_analyzer = self.analyzers[analyzer_key]
        else:
            raise ValueError(f"Unknown analyzer: {analyzer_key}")

    def configure_analyzer(self, analyzer_key, api_key):
        """配置指定的分析器"""
        if analyzer_key in self.analyzers:
            self.analyzers[analyzer_key].configure(api_key)
        else:
            raise ValueError(f"Unknown analyzer: {analyzer_key}")

    def analyze_image(self, image_path):
        """使用当前分析器分析图片"""
        if not self.current_analyzer:
            raise ValueError("No analyzer selected")
        if not self.current_analyzer.is_configured():
            raise ValueError("Current analyzer not configured")
        return self.current_analyzer.analyze_image(image_path)


class VideoAnalyzer(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()

        # 设置窗口标题和尺寸
        self.title("视频安全检查工具")
        self.geometry("1024x768")
        self.resizable(False, False)

        # 初始化配置管理器
        self.config_manager = ConfigManager()

        # 初始化分析相关的属性
        self.max_retries = 3
        self.retry_delay = 2
        self.concurrent_limit = 2
        self.request_semaphore = threading.Semaphore(self.concurrent_limit)
        self.analysis_results = {}

        # 初始化 AI 管理器
        self.ai_manager = AIManager()
        self.available_models = self.ai_manager.get_available_analyzers()

        # 创建 UI 变量
        self.enable_ai = tk.BooleanVar(value=self.config_manager.config.get('enable_ai', False))
        self.current_model = tk.StringVar(value=self.config_manager.config.get('current_model', ''))
        self.sensitivity_value = tk.StringVar(value=str(self.config_manager.config.get('sensitivity', 0.3)))

        # 创建所有 UI 控件
        self._create_ui()
        
        # 加载保存的配置
        self._load_saved_config()

    def _create_ui(self):
        """创建所有UI控件"""
        # 修改拖拽区域显示
        self.drop_frame = ttk.LabelFrame(self, text="将视频文件拖拽到这里")
        self.drop_frame.pack(padx=10, pady=10, fill=tk.X)
        
        # 添加视频信息标签
        self.video_info = ttk.Label(self.drop_frame, text="等待视频文件...", wraplength=700)
        self.video_info.pack(padx=10, pady=10)

        # 设置拖放目标
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.handle_drop)

        # 创建AI设置区域
        self.ai_settings_frame = ttk.LabelFrame(self, text="AI 分析设置")
        self.ai_settings_frame.pack(padx=10, pady=5, fill=tk.X)
        
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
        
        self.model_combobox = ttk.Combobox(
            self.ai_model_frame,
            textvariable=self.current_model,
            values=[model[1] for model in self.available_models],
            state='disabled'
        )
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

        # 添加配置文件目录按钮
        self.config_button = ttk.Button(
            self.ai_settings_frame,
            text="打开配置目录",
            command=self._open_config_dir
        )
        self.config_button.pack(padx=5, pady=5)

        # 创建设置区域
        self.settings_frame = ttk.LabelFrame(self, text="设置")
        self.settings_frame.pack(padx=10, pady=5, fill=tk.X)

        # 创建场景检测灵敏度滑动条
        self.sensitivity_frame = ttk.Frame(self.settings_frame)
        self.sensitivity_frame.pack(padx=5, pady=5, fill=tk.X)
        
        ttk.Label(self.sensitivity_frame, text="场景检测灵敏度:").pack(side=tk.LEFT, padx=5)
        
        # 先创建标签
        self.sensitivity_label = ttk.Label(self.sensitivity_frame, text="0.3")
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
        self.sensitivity_scale.set(0.3)  # 设置默认值

        # 修改预览区域的布局
        self.preview_frame = ttk.LabelFrame(self, text="关键帧预览")
        self.preview_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # 创建画布和滚动条的容器
        self.canvas_container = ttk.Frame(self.preview_frame)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # 创建画布
        self.canvas = tk.Canvas(self.canvas_container)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建垂直滚动条
        self.v_scrollbar = ttk.Scrollbar(self.canvas_container, orient="vertical", command=self.canvas.yview)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 配置画布
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)
        
        # 创建可滚动的框架
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

        # 添加状态标签
        self.status_label = ttk.Label(self, text="就绪")
        self.status_label.pack(padx=10, pady=5)

        # 添加进度条
        self.progress_frame = ttk.Frame(self)
        self.progress_frame.pack(padx=10, pady=5, fill=tk.X)
        
        self.progress_label = ttk.Label(self.progress_frame, text="")
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

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
                pass
        
        # 设置灵敏度
        if 'sensitivity' in config:
            self.sensitivity_scale.set(config['sensitivity'])
        
        # 更新 UI 状态
        self._toggle_ai_settings()

    def _save_config(self):
        """保存当前配置"""
        config = {
            'enable_ai': self.enable_ai.get(),
            'current_model': self.current_model.get(),
            'api_key': self.api_key_entry.get().strip(),  # 确保去除空白字符
            'sensitivity': float(self.sensitivity_scale.get())
        }
        print("Saving config:", config)  # 添加调试输出
        self.config_manager.save_config(config)

    def _toggle_ai_settings(self):
        """切换AI设置的启用状态"""
        state = 'normal' if self.enable_ai.get() else 'disabled'
        self.model_combobox.config(state=state)
        self.api_key_entry.config(state=state)
        
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

    def handle_drop(self, event):
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        file_path = file_path.strip('"')
        
        if not file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            messagebox.showerror("错误", "请拖入有效的视频文件！")
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
            
            # 配置AI分析器并保存配置
            model_key = next(key for key, name in self.available_models 
                            if name == self.current_model.get())
            self.ai_manager.configure_analyzer(model_key, self.api_key_entry.get())
            self.ai_manager.set_current_analyzer(model_key)
            self._save_config()
        
        self.process_video(file_path)

    def update_sensitivity_label(self, value):
        """更新灵敏度标签显示"""
        formatted_value = "{:.1f}".format(float(value))
        self.sensitivity_label.config(text=formatted_value)
        self.sensitivity_value.set(formatted_value)

    def process_video(self, video_path):
        self.status_label.config(text="正在处理视频，请稍候...")
        self.progress_label.config(text="准备处理...")
        self.progress_bar.start(10)  # 启动进度条动画
        self.update()

        # 清理预览区域
        for _, container in self.preview_images:
            container.destroy()
        self.preview_images.clear()
        self.processed_files.clear()

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
            # 创建输出目录
            video_dir = os.path.dirname(video_path)
            frames_dir = os.path.join(video_dir, 'tmp_frames')
            if not os.path.exists(frames_dir):
                os.makedirs(frames_dir)

            # 获取当前灵敏度值
            sensitivity = self.sensitivity_value.get()
            
            # 第一步：使用ffmpeg提取关键帧，改用jpg格式
            temp_pattern = os.path.join(frames_dir, 'temp_%04d.jpg').replace('\\', '/')
            
            extract_command = [
                'ffmpeg',
                '-i', video_path,
                '-vf', f"select='gt(scene,{sensitivity})'",
                '-vsync', 'vfr',
                '-q:v', '2',  # 添加JPEG质量设置
                temp_pattern
            ]

            # 执行提取命令
            process = subprocess.Popen(
                extract_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )

            # 读取输出并更新进度
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                # 检查是否生成了新的图片，修改为jpg格式
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
                            
                            # 创建新的文件名，使用jpg扩展名
                            new_filename = f'frame_{hours:02d}-{minutes:02d}-{seconds:02d}.{milliseconds:03d}.jpg'
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
                elif action == 'complete':
                    self.progress_bar.stop()
                    self.progress_label.config(text=f"完成！共提取 {len(self.processed_files)} 个关键帧")
                    self.status_label.config(text="处理完成")
                    messagebox.showinfo("完成", f"视频处理完成！\n共提取 {len(self.processed_files)} 个关键帧")
                    return
                elif action == 'error':
                    self.progress_bar.stop()
                    self.progress_label.config(text="处理失败")
                    self.status_label.config(text="处理失败")
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

            # 从文件名中提取时间码
            time_str = os.path.basename(image_path).replace('frame_', '').replace('.jpg', '')
            
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
            
            if response and (hasattr(response, 'choices') or isinstance(response, dict)):
                try:
                    # 获取原始内容
                    if isinstance(response, dict):
                        content = response['choices'][0]['message']['content']
                    else:
                        content = response.choices[0].message.content
                    
                    print(f"Raw API response for {image_path}:", content)
                    
                    # 清理 Markdown 代码块标记
                    content = re.sub(r'```json\s*', '', content)
                    content = re.sub(r'```\s*$', '', content)
                    content = content.strip()
                    
                    try:
                        # 直接解析清理后的 JSON
                        content_data = json.loads(content)
                    except json.JSONDecodeError:
                        # 如果解析失败，尝试进一步清理和修复
                        try:
                            json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                                json_str = re.sub(r'(?m)^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_str)
                                json_str = json_str.replace("'", '"')
                                content_data = json.loads(json_str)
                            else:
                                # 如果没有找到 JSON，从文本内容推断结果
                                content_lower = content.lower()
                                is_safe = all(word not in content_lower for word in [
                                    "不安全", "风险", "危险", "暴力", "恐怖", "血腥", 
                                    "敏感", "不适", "违规", "违法"
                                ])
                                risk_type = "未知" if not is_safe else ""
                                description = content.strip()
                                content_data = {
                                    "is_safe": is_safe,
                                    "risk_type": risk_type,
                                    "description": description
                                }
                        except Exception as e:
                            print(f"Error fixing JSON for {image_path}: {e}")
                            raise

                    # 提取和标准化结果
                    is_safe = content_data.get('is_safe', True)
                    if isinstance(is_safe, str):
                        is_safe = is_safe.lower() in ['true', '1', 'yes', '安全']
                    
                    risk_type = content_data.get('risk_type', '')
                    if not risk_type and not is_safe:
                        risk_type = "未知风险"
                    elif risk_type.lower() in ['无', 'none', '']:
                        risk_type = ""
                    
                    description = content_data.get('description', '')
                    if not description:
                        description = "无详细说明" if is_safe else "检测到潜在风险"

                    # 更新界面
                    self.after(0, lambda: self._update_analysis_result(
                        container, label, is_safe, risk_type, description))
                    
                    # 存储结果
                    self.analysis_results[image_path] = {
                        'is_safe': is_safe,
                        'risk_type': risk_type,
                        'description': description
                    }
                except Exception as e:
                    print(f"Error parsing result for {image_path}: {e}")
                    print(f"Raw content: {content}")
                    self.after(0, lambda: label.config(
                        text="解析失败", 
                        foreground="orange"))
            else:
                self.after(0, lambda: label.config(
                    text="分析失败", 
                    foreground="red"))

        except Exception as e:
            print(f"Error in analysis thread for {image_path}: {e}")
            self.after(0, lambda: label.config(
                text="分析出错", 
                foreground="red"))

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


if __name__ == '__main__':
    app = VideoAnalyzer()
    app.mainloop()
