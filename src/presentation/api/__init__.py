"""Web API层.

提供RESTful API接口，实现90秒闭环诊断流程。
"""

from src.presentation.api.main import create_app

__all__ = ["create_app"]
