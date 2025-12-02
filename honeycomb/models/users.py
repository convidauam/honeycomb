class DroneUser:
    def __init__(self, userid, display_name, username, icon=None, background=None):
        self.userid = userid
        self.display_name = display_name
        self.username = username
        self.icon = icon
        self.background = background

    def get_stats(self, key=None):
        if hasattr(self, "__stats__"):
            if key:
                return getattr(self.__stats__, key, None)
            else:
                return self.__stats__._asdict()
        return None