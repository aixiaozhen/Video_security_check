import json
import os

class ConfigManager:
    def __init__(self):
        # 获取用户目录下的配置文件路径
        self.config_dir = os.path.join(os.path.expanduser('~'), '.video_analyzer')
        self.config_file = os.path.join(self.config_dir, 'config.json')
        
        # 确保配置目录存在
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            
        # 默认配置
        self.default_config = {
            'enable_ai': False,
            'current_model': '',
            'api_key': '',
            'sensitivity': 0.3,
            'output_dir': '',
            'use_video_dir': True
        }
        
        # 加载配置，但不覆盖已存在的值
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    # 合并保存的配置和默认配置，保留已存在的值
                    config = self.default_config.copy()
                    config.update(saved_config)
                    return config
            return self.default_config.copy()
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.default_config.copy()
    
    def save_config(self, config):
        """保存配置到文件"""
        try:
            # 确保保存的配置包含所有必要的键
            full_config = self.default_config.copy()
            full_config.update(config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=2, ensure_ascii=False)
                
            # 更新当前配置
            self.config = full_config
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_config_dir(self):
        """获取配置文件目录"""
        return self.config_dir 