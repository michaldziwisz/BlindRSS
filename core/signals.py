class SignalManager:
    _subscribers = []
    
    @classmethod
    def subscribe(cls, callback):
        """Callback should accept (event_type, data)"""
        cls._subscribers.append(callback)
        
    @classmethod
    def emit(cls, event_type, data):
        for cb in cls._subscribers:
            try:
                cb(event_type, data)
            except Exception as e:
                print(f"Signal emit error: {e}")
