"""Common decorators used throughout the application
"""

from functools import wraps
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


def with_error_handling(func: Callable) -> Callable:
    """Decorator for error handling - abstracts exception management"""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(
                "operation_error",
                function=func.__name__,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    return wrapper


def with_logging(operation_name: str):
    """Decorator for operation logging - abstracts logging boilerplate"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            logger.debug("operation_started", operation=operation_name)

            try:
                result = await func(*args, **kwargs)
                logger.info(
                    "operation_completed", operation=operation_name, success=True
                )
                return result
            except Exception as e:
                logger.error(
                    "operation_failed",
                    operation=operation_name,
                    error=str(e),
                    success=False,
                )
                raise

        return wrapper

    return decorator
