from persistent import Persistent


class DroneUser(Persistent):
    def __init__(self, userid, display_name, username, icon=None, background=None):
        self.userid = userid
        self.display_name = display_name
        self.username = username
        self.icon = icon
        self.background = background

    def update_profile(self, display_name=None, username=None, icon=None, background=None):
        if display_name is not None:
            self.display_name = display_name
        if username is not None:
            self.username = username
        if icon is not None:
            self.icon = icon
        if background is not None:
            self.background = background

    def get_stats(self, key=None):
        if hasattr(self, "__stats__"):
            if key:
                return getattr(self.__stats__, key, None)
            else:
                return self.__stats__._asdict()
        return None
