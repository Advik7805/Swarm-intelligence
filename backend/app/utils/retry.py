"""
API call retry helpers
Retry logic for external API calls such as the LLM.
"""

import time
import random
import functools
from typing import Callable, Any, Optional, Type, Tuple
from ..utils.logger import get_logger

logger = get_logger('hivemind.retry')


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
        Retry decorator with exponential backoff.
    
    Args:
                max_retries: max attempts
                initial_delay: first delay (seconds)
                max_delay: delay cap (seconds)
                backoff_factor: backoff multiplier
                jitter: add random jitter?
                exceptions: exception types worth retrying
                on_retry: retry callback (exception, retry_count)
    
    Usage:
        @retry_with_backoff(max_retries=3)
        def call_llm_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} still failed after {max_retries} retries: {str(e)}")
                        raise
                    
                                        # compute the delay
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Function {func.__name__} attempt {attempt + 1} failed: {str(e)}, "
                        f"{current_delay:.1f}s; retrying..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    time.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_backoff_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
        Async variant of the retry decorator.
    """
    import asyncio
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Async function {func.__name__} still failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    current_delay = min(delay, max_delay)
                    if jitter:
                        current_delay = current_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Async function {func.__name__} attempt {attempt + 1} failed: {str(e)}, "
                        f"{current_delay:.1f}s; retrying..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt + 1)
                    
                    await asyncio.sleep(current_delay)
                    delay *= backoff_factor
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryableAPIClient:
    """
        Retryable API client wrapper.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def call_with_retry(
        self,
        func: Callable,
        *args,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        **kwargs
    ) -> Any:
        """
                Run a call and retry on failure.
        
        Args:
                        func: function to call
                        *args: positional args
                    exceptions: exception types worth retrying
                        **kwargs: keyword args
            
        Returns:
                        The function return value.
        """
        last_exception = None
        delay = self.initial_delay
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except exceptions as e:
                last_exception = e
                
                if attempt == self.max_retries:
                    logger.error(f"API call still failed after {self.max_retries} retries: {str(e)}")
                    raise
                
                current_delay = min(delay, self.max_delay)
                current_delay = current_delay * (0.5 + random.random())
                
                logger.warning(
                    f"API call attempt {attempt + 1} failed: {str(e)}, "
                    f"{current_delay:.1f}s; retrying..."
                )
                
                time.sleep(current_delay)
                delay *= self.backoff_factor
        
        raise last_exception
    
    def call_batch_with_retry(
        self,
        items: list,
        process_func: Callable,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        continue_on_failure: bool = True
    ) -> Tuple[list, list]:
        """
                Process a batch, retrying each failed item individually.
        
        Args:
                        items: items to process
                        process_func: handler taking a single item
                    exceptions: exception types worth retrying
                        continue_on_failure: keep going after one item fails?
            
        Returns:
                        (successful results, failed items)
        """
        results = []
        failures = []
        
        for idx, item in enumerate(items):
            try:
                result = self.call_with_retry(
                    process_func,
                    item,
                    exceptions=exceptions
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to process item {idx + 1}: {str(e)}")
                failures.append({
                    "index": idx,
                    "item": item,
                    "error": str(e)
                })
                
                if not continue_on_failure:
                    raise
        
        return results, failures

