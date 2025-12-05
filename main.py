import sys
import warnings
from dateutil.parser import UnknownTimezoneWarning
warnings.filterwarnings("ignore", category=UnknownTimezoneWarning)

import multiprocessing

# Ensure dependencies are present before importing GUI
# Only runs when running from source (not frozen)
if not getattr(sys, 'frozen', False):
    try:
        from core.dependency_check import check_and_install_dependencies
        check_and_install_dependencies()
    except ImportError:
        pass 

import wx
from core.config import ConfigManager
from core.factory import get_provider
from gui.mainframe import MainFrame
import logging
import os
import sys

class RSSApp(wx.App):
    def OnInit(self):
        # Configure logging to file and console
        log_file_path = os.path.join(os.getcwd(), 'blindrss_debug.log')
        
        if os.environ.get("BLINDRSS_DEBUG"):
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file_path, mode='w'),
                    logging.StreamHandler(sys.stdout)
                ]
            )
        else:
            # No logging for release builds
            logging.basicConfig(level=logging.CRITICAL, handlers=[logging.NullHandler()])
        
        self.config_manager = ConfigManager()
        self.provider = get_provider(self.config_manager)
        
        self.frame = MainFrame(self.provider, self.config_manager)
        self.frame.Show()
        return True

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = RSSApp()
    app.MainLoop()
