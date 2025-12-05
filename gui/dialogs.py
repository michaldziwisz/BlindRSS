import wx
import math

class AddFeedDialog(wx.Dialog):
    def __init__(self, parent, categories):
        super().__init__(parent, title="Add Feed")
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        hbox1.Add(wx.StaticText(self, label="URL:"), flag=wx.RIGHT, border=8)
        self.tc_url = wx.TextCtrl(self)
        hbox1.Add(self.tc_url, proportion=1)
        btn_search = wx.Button(self, label="Search Podcasts")
        btn_search.Bind(wx.EVT_BUTTON, self.on_search)
        hbox1.Add(btn_search, flag=wx.LEFT, border=8)
        vbox.Add(hbox1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)
        
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        hbox2.Add(wx.StaticText(self, label="Category:"), flag=wx.RIGHT, border=8)
        self.cb_category = wx.ComboBox(self, choices=categories, style=wx.CB_DROPDOWN)
        if "Uncategorized" in categories:
            self.cb_category.SetValue("Uncategorized")
        hbox2.Add(self.cb_category, proportion=1)
        vbox.Add(hbox2, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)
        
        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btns, flag=wx.EXPAND|wx.ALL, border=10)
        
        self.SetSizer(vbox)
        self.Fit()

    def get_data(self):
        return self.tc_url.GetValue(), self.cb_category.GetValue()

    def on_search(self, event):
        dlg = PodcastSearchDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.get_selected_url()
            if url:
                self.tc_url.SetValue(url)
        dlg.Destroy()

class SettingsDialog(wx.Dialog):
    def __init__(self, parent, config):
        super().__init__(parent, title="Settings", size=(500, 600))
        self.config = config
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        panel = wx.Panel(self)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Notebook for All Settings
        nb = wx.Notebook(panel)
        
        # General Tab
        self.p_gen = wx.Panel(nb)
        self._init_general_tab(self.p_gen)
        nb.AddPage(self.p_gen, "General")
        
        # Miniflux Tab
        self.p_mf = wx.Panel(nb)
        self._init_miniflux_tab(self.p_mf)
        nb.AddPage(self.p_mf, "Miniflux")
        
        # TheOldReader Tab
        self.p_tor = wx.Panel(nb)
        self._init_tor_tab(self.p_tor)
        nb.AddPage(self.p_tor, "TheOldReader")
        
        # Inoreader Tab
        self.p_ino = wx.Panel(nb)
        self._init_ino_tab(self.p_ino)
        nb.AddPage(self.p_ino, "Inoreader")
        
        # BazQux Tab
        self.p_bz = wx.Panel(nb)
        self._init_bz_tab(self.p_bz)
        nb.AddPage(self.p_bz, "BazQux")
        
        panel_sizer.Add(nb, 1, wx.EXPAND|wx.ALL, 10)
        
        panel.SetSizer(panel_sizer)
        
        main_sizer.Add(panel, 1, wx.EXPAND)
        
        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        main_sizer.Add(btns, flag=wx.EXPAND|wx.ALL, border=10)
        
        self.SetSizer(main_sizer)

    def _init_general_tab(self, p):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Active Provider
        hbox_prov = wx.BoxSizer(wx.HORIZONTAL)
        hbox_prov.Add(wx.StaticText(p, label="Active Provider:"), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=8)
        self.cb_provider = wx.ComboBox(p, choices=["local", "miniflux", "theoldreader", "inoreader", "bazqux"], style=wx.CB_READONLY)
        self.cb_provider.SetValue(self.config.get("active_provider", "local"))
        hbox_prov.Add(self.cb_provider, proportion=1)
        sizer.Add(hbox_prov, flag=wx.EXPAND|wx.ALL, border=10)
        
        # Refresh Interval
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        hbox1.Add(wx.StaticText(p, label="Refresh Interval (seconds):"), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=8)
        self.sp_refresh = wx.SpinCtrl(p, min=30, max=3600, initial=int(self.config.get("refresh_interval", 300)))
        hbox1.Add(self.sp_refresh, proportion=1)
        sizer.Add(hbox1, flag=wx.EXPAND|wx.ALL, border=10)
        
        # Skip Silence (Global)
        self.chk_skip_silence = wx.CheckBox(p, label="Skip Silence (Global)")
        self.chk_skip_silence.SetToolTip("Automatically skip detected silence in all podcasts")
        self.chk_skip_silence.SetValue(self.config.get("skip_silence", False))
        sizer.Add(self.chk_skip_silence, flag=wx.ALL, border=10)

        # Close to tray
        self.chk_close_tray = wx.CheckBox(p, label="Close button sends app to system tray")
        self.chk_close_tray.SetValue(self.config.get("close_to_tray", False))
        sizer.Add(self.chk_close_tray, flag=wx.ALL, border=10)

        # Max concurrent downloads
        hbox_dl = wx.BoxSizer(wx.HORIZONTAL)
        hbox_dl.Add(wx.StaticText(p, label="Max concurrent downloads:"), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=8)
        self.sp_max_dl = wx.SpinCtrl(p, min=1, max=20, initial=int(self.config.get("max_downloads", 10)))
        hbox_dl.Add(self.sp_max_dl, proportion=0)
        sizer.Add(hbox_dl, flag=wx.EXPAND|wx.ALL, border=10)

        # Auto Download
        sb_auto = wx.StaticBoxSizer(wx.VERTICAL, p, "Automatic Downloads")
        
        self.chk_auto_dl = wx.CheckBox(p, label="Automatically download all podcasts")
        self.chk_auto_dl.SetValue(self.config.get("auto_download_podcasts", False))
        sb_auto.Add(self.chk_auto_dl, flag=wx.ALL, border=5)
        
        hbox_period = wx.BoxSizer(wx.HORIZONTAL)
        hbox_period.Add(wx.StaticText(p, label="Download period:"), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=5)
        
        self.period_map = [
            ("1 Day", "1d"), ("5 Days", "5d"), ("1 Week", "1w"), ("2 Weeks", "2w"),
            ("1 Month", "1m"), ("3 Months", "3m"), ("6 Months", "6m"),
            ("1 Year", "1y"), ("2 Years", "2y"), ("5 Years", "5y"),
            ("10 Years", "10y"), ("Unlimited", "unlimited")
        ]
        choices = [x[0] for x in self.period_map]
        self.cb_period = wx.ComboBox(p, choices=choices, style=wx.CB_READONLY)
        
        # Set selection
        current = self.config.get("auto_download_period", "1w")
        sel_idx = 2
        for i, (label, val) in enumerate(self.period_map):
            if val == current:
                sel_idx = i
                break
        self.cb_period.SetSelection(sel_idx)
        
        hbox_period.Add(self.cb_period, proportion=1)
        sb_auto.Add(hbox_period, flag=wx.EXPAND|wx.ALL, border=5)
        
        sizer.Add(sb_auto, flag=wx.EXPAND|wx.ALL, border=10)
        
        p.SetSizer(sizer)

    def _init_miniflux_tab(self, p):
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 2, 5, 5)
        
        grid.Add(wx.StaticText(p, label="URL:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_mf_url = wx.TextCtrl(p)
        self.tc_mf_url.SetValue(self.config.get("providers", {}).get("miniflux", {}).get("url", ""))
        grid.Add(self.tc_mf_url, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(p, label="API Key:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_mf_key = wx.TextCtrl(p)
        self.tc_mf_key.SetValue(self.config.get("providers", {}).get("miniflux", {}).get("api_key", ""))
        grid.Add(self.tc_mf_key, 1, wx.EXPAND)
        
        btn_test = wx.Button(p, label="Test Connection")
        btn_test.Bind(wx.EVT_BUTTON, self.on_test_miniflux)
        grid.Add(btn_test, 0)
        
        grid.AddGrowableCol(1, 1)
        sizer.Add(grid, 1, wx.EXPAND|wx.ALL, 10)
        p.SetSizer(sizer)

    def _init_tor_tab(self, p):
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(2, 2, 5, 5)
        
        grid.Add(wx.StaticText(p, label="Email:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_tor_email = wx.TextCtrl(p)
        self.tc_tor_email.SetValue(self.config.get("providers", {}).get("theoldreader", {}).get("email", ""))
        grid.Add(self.tc_tor_email, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(p, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_tor_pass = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        self.tc_tor_pass.SetValue(self.config.get("providers", {}).get("theoldreader", {}).get("password", ""))
        grid.Add(self.tc_tor_pass, 1, wx.EXPAND)
        
        grid.AddGrowableCol(1, 1)
        sizer.Add(grid, 1, wx.EXPAND|wx.ALL, 10)
        p.SetSizer(sizer)
        
    def _init_ino_tab(self, p):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(p, label="API Token:"), 0, wx.ALL, 5)
        self.tc_ino_token = wx.TextCtrl(p)
        self.tc_ino_token.SetValue(self.config.get("providers", {}).get("inoreader", {}).get("token", ""))
        sizer.Add(self.tc_ino_token, 0, wx.EXPAND|wx.ALL, 5)
        p.SetSizer(sizer)

    def _init_bz_tab(self, p):
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(2, 2, 5, 5)
        
        grid.Add(wx.StaticText(p, label="Email:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_bz_email = wx.TextCtrl(p)
        self.tc_bz_email.SetValue(self.config.get("providers", {}).get("bazqux", {}).get("email", ""))
        grid.Add(self.tc_bz_email, 1, wx.EXPAND)
        
        grid.Add(wx.StaticText(p, label="Password:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.tc_bz_pass = wx.TextCtrl(p, style=wx.TE_PASSWORD)
        self.tc_bz_pass.SetValue(self.config.get("providers", {}).get("bazqux", {}).get("password", ""))
        grid.Add(self.tc_bz_pass, 1, wx.EXPAND)
        
        grid.AddGrowableCol(1, 1)
        sizer.Add(grid, 1, wx.EXPAND|wx.ALL, 10)
        p.SetSizer(sizer)

    def on_test_miniflux(self, event):
        # Logic moved here or duplicated for quick fix, ideally shared
        try:
            from providers.miniflux import MinifluxProvider
            prov = MinifluxProvider({"providers": {"miniflux": {"url": self.tc_mf_url.GetValue(), "api_key": self.tc_mf_key.GetValue()}}})
            if prov.test_connection():
                wx.MessageBox("Connection Successful!", "Success")
            else:
                wx.MessageBox("Connection Failed.", "Error")
        except: pass

    def get_data(self):
        # Update config structure
        if "providers" not in self.config: self.config["providers"] = {}
        
        # Miniflux
        if "miniflux" not in self.config["providers"]: self.config["providers"]["miniflux"] = {}
        self.config["providers"]["miniflux"]["url"] = self.tc_mf_url.GetValue()
        self.config["providers"]["miniflux"]["api_key"] = self.tc_mf_key.GetValue()
        
        # TheOldReader
        if "theoldreader" not in self.config["providers"]: self.config["providers"]["theoldreader"] = {}
        self.config["providers"]["theoldreader"]["email"] = self.tc_tor_email.GetValue()
        self.config["providers"]["theoldreader"]["password"] = self.tc_tor_pass.GetValue()
        
        # Inoreader
        if "inoreader" not in self.config["providers"]: self.config["providers"]["inoreader"] = {}
        self.config["providers"]["inoreader"]["token"] = self.tc_ino_token.GetValue()
        
        # BazQux
        if "bazqux" not in self.config["providers"]: self.config["providers"]["bazqux"] = {}
        self.config["providers"]["bazqux"]["email"] = self.tc_bz_email.GetValue()
        self.config["providers"]["bazqux"]["password"] = self.tc_bz_pass.GetValue()
        
        # Find selected period value
        sel = self.cb_period.GetSelection()
        period_val = self.period_map[sel][1] if 0 <= sel < len(self.period_map) else "1w"

        return {
            "refresh_interval": self.sp_refresh.GetValue(),
            "active_provider": self.cb_provider.GetValue(),
            "skip_silence": self.chk_skip_silence.GetValue(),
            "close_to_tray": self.chk_close_tray.GetValue(),
            "max_downloads": self.sp_max_dl.GetValue(),
            "auto_download_podcasts": self.chk_auto_dl.GetValue(),
            "auto_download_period": period_val,
            "providers": self.config["providers"]
        }


class PodcastSearchDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Search Podcasts", size=(600, 500))
        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(wx.StaticText(self, label="Query:"), flag=wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, border=5)
        self.tc_query = wx.TextCtrl(self)
        hbox.Add(self.tc_query, 1, wx.EXPAND|wx.RIGHT, 5)
        btn_search = wx.Button(self, label="Search")
        btn_search.Bind(wx.EVT_BUTTON, self.on_search)
        hbox.Add(btn_search, 0)
        vbox.Add(hbox, 0, wx.EXPAND|wx.ALL, 10)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN)
        self.list.InsertColumn(0, "Title", width=300)
        self.list.InsertColumn(1, "Author", width=180)
        self.list.InsertColumn(2, "Feed URL", width=400)
        vbox.Add(self.list, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)

        btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        vbox.Add(btns, 0, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(vbox)
        self.results = []

    def on_search(self, event):
        import requests, urllib.parse
        term = self.tc_query.GetValue().strip()
        if not term:
            return
        url = f"https://itunes.apple.com/search?media=podcast&term={urllib.parse.quote(term)}&limit=20"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self.results = data.get("results", [])
            self.populate_results()
        except Exception as e:
            wx.MessageBox(f"Search failed: {e}", "Error", wx.ICON_ERROR)

    def populate_results(self):
        self.list.DeleteAllItems()
        for i, r in enumerate(self.results):
            title = r.get("collectionName") or r.get("trackName") or ""
            author = r.get("artistName", "")
            feed = r.get("feedUrl", "")
            idx = self.list.InsertItem(i, title)
            self.list.SetItem(idx, 1, author)
            self.list.SetItem(idx, 2, feed)

    def get_selected_url(self):
        idx = self.list.GetFirstSelected()
        if idx == -1 or idx >= len(self.results):
            return None
        return self.results[idx].get("feedUrl")


class DownloadManagerDialog(wx.Dialog):
    def __init__(self, parent, downloader):
        super().__init__(parent, title="Download Manager", size=(800, 400))
        self.downloader = downloader
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.list = wx.ListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN)
        self.list.InsertColumn(0, "Title", width=320)
        self.list.InsertColumn(1, "Status", width=100)
        self.list.InsertColumn(2, "Progress", width=100)
        self.list.InsertColumn(3, "Target / Error", width=240)
        vbox.Add(self.list, 1, wx.EXPAND|wx.ALL, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_pause = wx.Button(self, label="Pause")
        self.btn_resume = wx.Button(self, label="Resume")
        self.btn_cancel = wx.Button(self, label="Cancel")
        self.btn_cancel_all = wx.Button(self, label="Cancel All")
        for b in [self.btn_pause, self.btn_resume, self.btn_cancel, self.btn_cancel_all]:
            btn_sizer.Add(b, 0, wx.RIGHT, 5)
        vbox.Add(btn_sizer, 0, wx.ALIGN_LEFT|wx.LEFT|wx.RIGHT|wx.BOTTOM, 8)

        btns = self.CreateButtonSizer(wx.CLOSE)
        vbox.Add(btns, 0, wx.ALIGN_RIGHT|wx.ALL, 8)

        self.SetSizer(vbox)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(500)
        self.Bind(wx.EVT_BUTTON, self.on_close, id=wx.ID_CLOSE)
        self.btn_pause.Bind(wx.EVT_BUTTON, self.on_pause)
        self.btn_resume.Bind(wx.EVT_BUTTON, self.on_resume)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.btn_cancel_all.Bind(wx.EVT_BUTTON, self.on_cancel_all)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.refresh()

    def on_close(self, event):
        if self.timer.IsRunning():
            self.timer.Stop()
        self.Destroy()

    def on_timer(self, event):
        self.refresh()

    def refresh(self):
        jobs = self.downloader.get_jobs_snapshot() if self.downloader else []
        self.list.Freeze()
        self.list.DeleteAllItems()
        for i, j in enumerate(jobs):
            status = j.get("status", "")
            prog = j.get("progress", 0.0)
            prog_str = f"{int(math.floor(prog*100))}%"
            msg = j.get("error") or j.get("target", "")
            idx = self.list.InsertItem(i, j.get("title", ""))
            self.list.SetItem(idx, 1, status)
            self.list.SetItem(idx, 2, prog_str)
            self.list.SetItem(idx, 3, msg)
        self.list.Thaw()

    def _selected_index(self):
        idx = self.list.GetFirstSelected()
        return idx if idx != -1 else None

    def on_pause(self, event):
        idx = self._selected_index()
        if idx is not None:
            self.downloader.pause_job(idx)
            self.refresh()

    def on_resume(self, event):
        idx = self._selected_index()
        if idx is not None:
            self.downloader.resume_job(idx)
            self.refresh()

    def on_cancel(self, event):
        idx = self._selected_index()
        if idx is not None:
            self.downloader.cancel_job(idx)
            self.refresh()

    def on_cancel_all(self, event):
        self.downloader.cancel_all()
        self.refresh()
