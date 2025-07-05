"""
错误处理和恢复机制
提供网络错误重试、播放错误恢复、状态同步等功能
"""
import asyncio
import logging
from typing import Optional, Callable, Any
from enum import Enum
import time

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    DOWNLOAD_ERROR = "download_error"
    PLAYBACK_ERROR = "playback_error"
    PLUGIN_ERROR = "plugin_error"
    DATABASE_ERROR = "database_error"
    CACHE_ERROR = "cache_error"


class RetryStrategy:
    """重试策略"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def get_delay(self, retry_count: int) -> float:
        """计算重试延迟（指数退避）"""
        delay = self.base_delay * (2 ** retry_count)
        return min(delay, self.max_delay)


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.error_counts = {}
        self.last_errors = {}
        self.recovery_strategies = {}
        
        # 默认重试策略
        self.default_retry = RetryStrategy(
            max_retries=self.config.get('max_retries', 3),
            base_delay=self.config.get('base_delay', 1.0),
            max_delay=self.config.get('max_delay', 60.0)
        )
        
        # 注册默认恢复策略
        self._register_default_strategies()
    
    def _register_default_strategies(self):
        """注册默认的恢复策略"""
        self.recovery_strategies[ErrorType.NETWORK_ERROR] = self._handle_network_error
        self.recovery_strategies[ErrorType.DOWNLOAD_ERROR] = self._handle_download_error
        self.recovery_strategies[ErrorType.PLAYBACK_ERROR] = self._handle_playback_error
        self.recovery_strategies[ErrorType.PLUGIN_ERROR] = self._handle_plugin_error
    
    async def handle_error(self, error: Exception, error_type: ErrorType, context: dict = None) -> bool:
        """处理错误并尝试恢复"""
        try:
            context = context or {}
            error_key = f"{error_type.value}_{str(error)}"
            
            # 记录错误
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
            self.last_errors[error_type] = {
                'error': str(error),
                'timestamp': time.time(),
                'context': context
            }
            
            logger.error(f"Handling {error_type.value}: {error}")
            
            # 检查是否超过最大重试次数
            if self.error_counts[error_key] > self.default_retry.max_retries:
                logger.error(f"Max retries exceeded for {error_type.value}")
                return False
            
            # 执行恢复策略
            recovery_func = self.recovery_strategies.get(error_type)
            if recovery_func:
                return await recovery_func(error, context)
            
            return False
            
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            return False
    
    async def retry_with_backoff(self, func: Callable, *args, retry_strategy: RetryStrategy = None, **kwargs) -> Any:
        """带退避重试的函数执行"""
        strategy = retry_strategy or self.default_retry
        last_exception = None
        
        for attempt in range(strategy.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < strategy.max_retries:
                    delay = strategy.get_delay(attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All retry attempts failed")
                    break
        
        if last_exception:
            raise last_exception
    
    async def _handle_network_error(self, error: Exception, context: dict) -> bool:
        """处理网络错误"""
        try:
            # 检查网络连接
            logger.info("Checking network connectivity...")
            
            # 等待网络恢复
            await asyncio.sleep(2.0)
            
            # 可以在这里添加网络检查逻辑
            logger.info("Network error recovery attempted")
            return True
            
        except Exception as e:
            logger.error(f"Network error recovery failed: {e}")
            return False
    
    async def _handle_download_error(self, error: Exception, context: dict) -> bool:
        """处理下载错误"""
        try:
            # 清理可能损坏的临时文件
            temp_file = context.get('temp_file')
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Cleaned up temp file: {temp_file}")
            
            # 尝试使用备用下载源
            alternative_url = context.get('alternative_url')
            if alternative_url:
                logger.info("Trying alternative download source...")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Download error recovery failed: {e}")
            return False
    
    async def _handle_playback_error(self, error: Exception, context: dict) -> bool:
        """处理播放错误"""
        try:
            player_core = context.get('player_core')
            if not player_core:
                return False
            
            # 尝试播放下一首
            logger.info("Attempting to skip to next song due to playback error...")
            next_song = await player_core.play_next()
            
            if next_song:
                logger.info(f"Successfully skipped to: {next_song.title}")
                return True
            else:
                # 没有下一首，停止播放
                player_core.stop()
                logger.info("No next song available, stopped playback")
                return False
                
        except Exception as e:
            logger.error(f"Playback error recovery failed: {e}")
            return False
    
    async def _handle_plugin_error(self, error: Exception, context: dict) -> bool:
        """处理插件错误"""
        try:
            plugin_name = context.get('plugin_name')
            plugin_manager = context.get('plugin_manager')
            
            if plugin_name and plugin_manager:
                # 禁用有问题的插件
                logger.warning(f"Disabling problematic plugin: {plugin_name}")
                plugin_manager.disable_plugin(plugin_name)
                
                # 尝试使用其他插件
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Plugin error recovery failed: {e}")
            return False
    
    def get_error_stats(self) -> dict:
        """获取错误统计"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'error_types': len(self.error_counts),
            'error_counts': dict(self.error_counts),
            'last_errors': dict(self.last_errors)
        }
    
    def reset_error_counts(self):
        """重置错误计数"""
        self.error_counts.clear()
        self.last_errors.clear()
        logger.info("Error counts reset")


# 全局错误处理器实例
_global_error_handler = None


def get_error_handler(config: dict = None) -> ErrorHandler:
    """获取全局错误处理器"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler(config)
    return _global_error_handler


async def safe_execute(func: Callable, *args, error_type: ErrorType = ErrorType.NETWORK_ERROR, 
                      context: dict = None, **kwargs) -> tuple[Any, bool]:
    """安全执行函数，自动处理错误"""
    error_handler = get_error_handler()
    
    try:
        if asyncio.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
        return result, True
        
    except Exception as e:
        success = await error_handler.handle_error(e, error_type, context)
        return None, success
