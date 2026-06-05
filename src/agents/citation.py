class CitationAgent:
    def __init__(self, provider=None):
        self._provider = provider
        self._name = "citation"

    def execute(self, *args, **kwargs):
        return None

    @property
    def name(self):
        return self._name
