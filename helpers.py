"""
工具函数模块

提供各种辅助工具和装饰器
"""

from typing import Callable, Any, Optional, Dict
from functools import wraps
import time
import json


def timer(func: Callable) -> Callable:
    """计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"[{func.__name__}] 执行时间: {elapsed:.2f}秒")
        return result
    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def log_call(func: Callable) -> Callable:
    """日志装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[调用] {func.__name__}(args={args}, kwargs={kwargs})")
        result = func(*args, **kwargs)
        print(f"[返回] {func.__name__} -> {result}")
        return result
    return wrapper


class Logger:
    """简单日志器"""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.log_file = log_file
    
    def _write(self, level: str, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] [{self.name}] {message}"
        print(log_line)
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + "\n")
    
    def info(self, message: str):
        self._write("INFO", message)
    
    def debug(self, message: str):
        self._write("DEBUG", message)
    
    def warning(self, message: str):
        self._write("WARNING", message)
    
    def error(self, message: str):
        self._write("ERROR", message)


def format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def parse_json_safe(text: str) -> Optional[Dict[str, Any]]:
    """安全解析JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def ensure_list(value: Any) -> list:
    """确保返回列表"""
    if isinstance(value, list):
        return value
    elif value is None:
        return []
    return [value]
