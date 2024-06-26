class BaseNotifier:
    def __init__(self, **kwargs):
        pass

    def notify(self, title: str, message: str, urgent: bool = False) -> None:
        raise NotImplementedError

    @property
    def enabled(self) -> bool:
        raise NotImplementedError
