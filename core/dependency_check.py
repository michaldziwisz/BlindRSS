import subprocess
import sys
import importlib.metadata

def check_and_install_dependencies():
    """
    Checks for required packages and installs/updates them silently if missing.
    """
    required = {'yt-dlp', 'wxpython', 'feedparser', 'requests', 'beautifulsoup4', 'python-dateutil', 'mutagen'}
    # pkg_resources is deprecated; use importlib.metadata instead
    installed = set()
    for dist in importlib.metadata.distributions():
        name_val = dist.metadata.get("Name") or dist.name
        if name_val:
            installed.add(name_val.lower())
    missing = required - installed

    if missing:
        # print(f"Missing dependencies: {missing}. Installing...")
        try:
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', *missing],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass # Fail silently as requested

    # Always try to update yt-dlp specifically
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
