
from __future__ import annotations
from typing import Optional

_service = None

def set_service(service):
    global _service
    _service = service

def get_service():
    return _service
