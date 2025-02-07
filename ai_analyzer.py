from abc import ABC, abstractmethod
import json
import base64
from zhipuai import ZhipuAI
import time
import re


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
                    model="glm-4v-flash",
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
