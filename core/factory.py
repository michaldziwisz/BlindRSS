from providers.local import LocalProvider
from providers.miniflux import MinifluxProvider
from providers.theoldreader import TheOldReaderProvider
from providers.inoreader import InoreaderProvider
from providers.bazqux import BazQuxProvider
from core.db import init_db

def get_provider(config_manager):
    # Ensure DB is initialized for all providers (needed for chapters/cache)
    init_db()
    
    active = config_manager.get("active_provider", "local")
    config = config_manager.config
    
    if active == "local":
        return LocalProvider(config)
    elif active == "miniflux":
        return MinifluxProvider(config)
    elif active == "theoldreader":
        return TheOldReaderProvider(config)
    elif active == "inoreader":
        return InoreaderProvider(config)
    elif active == "bazqux":
        return BazQuxProvider(config)
    
    return LocalProvider(config)
