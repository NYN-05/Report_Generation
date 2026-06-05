from typing import Optional

class FormattingAgent:
    def __init__(self, provider=None):
        self._provider = provider
        self._name = "formatting"

    def execute(self, *args, **kwargs):
        return None

    @property
    def name(self):
        return self._name
