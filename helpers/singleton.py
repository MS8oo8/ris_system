

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *arg, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*arg, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]