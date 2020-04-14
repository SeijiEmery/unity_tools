import os
import re
import plistlib
from .utils import search_filesystem


def locate_unity_versions_macos():
    return locate_macos_apps_with_executable_name('Unity')


class MacOSApplication:
    def __init__(self, app_path):
        self.app_path = app_path
        executable_dir = os.path.join(app_path, 'Contents/MacOS')
        if not app_path.endswith('.app') or not os.path.exists(executable_dir):
            raise Exception("'%s' is not an app bundle!" % app_path)

        plist_path = os.path.join(self.app_path, 'Contents/Info.plist')
        self.plist = plistlib.readPlist(plist_path)
        self.exec_path = os.path.join(app_path, 'Contents/MacOS',
                                      self.plist['CFBundleExecutable'])

    def version(self):
        return self.plist['CFBundleShortVersionString']

    def executable(self):
        return self.exec_path


def locate_macos_apps(search_paths=['/Applications'], visited=None,
                      recursion_depth_limit=None,
                      skip_files=('Extensions', 'Documentation',
                                  r'.*localized', 'Frameworks',
                                  'PlaybackEngines', 'plugins')):
    filter_regex = re.compile(
        '|'.join([pattern.lower() for pattern in skip_files]))
    # print(filter_regex)

    def blacklist(file, path):
        return re.match(filter_regex, file.lower()) is not None

    return search_filesystem(search_paths=search_paths,
                             predicate=lambda path: path.endswith('.app'),
                             blacklist=blacklist,
                             visited=visited,
                             recursion_depth_limit=recursion_depth_limit)


def locate_macos_apps_with_executable_name(name, *args, **kwargs):
    for app_path in locate_macos_apps(*args, **kwargs):
        if os.path.exists(os.path.join(app_path, 'Contents/MacOS', name)):
            yield MacOSApplication(app_path)
