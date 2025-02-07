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
        return "智谱 GLM-4V-Flash"

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
                print(f"API Error: {error_str}")  # 添加调试输出
                
                # 检查欠费错误
                if '"code":"1113"' in error_str or "账户已欠费" in error_str:
                    raise Exception("AI服务账户已欠费，请充值后重试") from e
                elif "429" in error_str:
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

    def parse_response(self, response):
        """解析API响应"""
        if not response or not (hasattr(response, 'choices') or isinstance(response, dict)):
            raise ValueError("Invalid response format")

        try:
            # 获取原始内容
            if isinstance(response, dict):
                content = response['choices'][0]['message']['content']
            else:
                content = response.choices[0].message.content
            
            print(f"Raw API response:", content)
            
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
                        content_data = {
                            "is_safe": is_safe,
                            "risk_type": "未知" if not is_safe else "",
                            "description": content.strip()
                        }
                except Exception as e:
                    raise ValueError(f"Error fixing JSON: {e}")

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

            return {
                'is_safe': is_safe,
                'risk_type': risk_type,
                'description': description
            }
            
        except Exception as e:
            raise ValueError(f"Error parsing response: {e}")


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
