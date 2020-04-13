import os
import subprocess
import re


class BlenderRunner:
    def __init__(self):
        pass

    def run_script(self, script, args):
        pass


class CommandlineBlenderRunner(BlenderRunner):
    def __init__(self, cmd='blender'):
        super().__init__()
        self.cmd = cmd

    def run_script(self, script, args):
        args = args.split() if type(args) != list else args
        cmd = self.cmd.split() + ['-b', '-p', script] + args
        return subprocess.run(cmd)

    def version(self):
        cmd = self.cmd.split()
        output = subprocess.check_output(cmd + ['--version']).decode('utf-8')
        version = output.split('\n')[0].lower().lstrip('blender ')
        version = re.sub(r'\([^\)]*\)', '', version).strip()
        return version


class ProgramBlenderRunner(CommandlineBlenderRunner):
    def __init__(self, path):
        self.path = path
        super().__init__(path)


class MacOSApplication:
    def __init__(self, app_path):
        self.app_path = app_path
        executable_dir = os.path.join(app_path, 'Contents/MacOS')
        if not app_path.endswith('.app') or not os.path.exists(executable_dir):
            raise Exception("'%s' is not an app bundle!" % app_path)

        import plistlib
        plist_path = os.path.join(self.app_path, 'Contents/Info.plist')
        self.plist = plistlib.readPlist(plist_path)
        self.exec_path = os.path.join(app_path, 'Contents/MacOS', self.plist['CFBundleExecutable'])

    def version(self):
        # print(self.plist)
        # print(self.plist.keys())
        return self.plist['CFBundleShortVersionString']


class MacOSBlenderRunner(ProgramBlenderRunner):
    def __init__(self, app):
        self.app = app
        super().__init__(self.app.exec_path)

    def version(self):
        v1 = super().version()
        v2 = self.app.version()
        return v1, v2


def search_filesystem(search_paths, predicate, blacklist, visited=None, recursion_depth_limit=None):
    if visited is None:
        visited = set()

    if type(search_paths) == str:
        search_paths = (search_paths,)

    unvisited = list()
    under_recursion_limit = \
        lambda x: True if recursion_depth_limit is None else \
        lambda x: x < recursion_depth_limit

    can_recurse = under_recursion_limit(0)
    for path in search_paths:
        if path in visited:
            continue
        if predicate(path):
            yield path
        elif can_recurse and os.path.isdir(path):
            unvisited.append((path, 1))

    while len(unvisited) > 0:
        search_path, depth = unvisited.pop()
        can_recurse = under_recursion_limit(depth)
        # print(type(search_path), search_path, depth, can_recurse)
        for file in os.listdir(search_path):
            # print("visiting '%s'" % search_path)
            path = os.path.join(search_path, file)
            if path in visited:
                # print("skippping '%s'" % path)
                continue
            if predicate(path):
                # print("returning '%s'" % path)
                yield path
            elif can_recurse and os.path.isdir(path) and not blacklist(file, path):
                unvisited.append((path, depth + 1))


def locate_macos_apps(search_paths=['/Applications'], visited=None, recursion_depth_limit=None,
                      skip_files=('Extensions', 'Documentation', r'.*localized', 'Frameworks', 'PlaybackEngines', 'plugins')):
    filter_regex = re.compile(
        '|'.join([pattern.lower() for pattern in skip_files]))
    # print(filter_regex)

    def blacklist(file, path): return re.match(
        filter_regex, file.lower()) is not None

    return search_filesystem(
        search_paths=search_paths,
        predicate=lambda path: path.endswith('.app'),
        blacklist=blacklist,
        visited=visited,
        recursion_depth_limit=recursion_depth_limit)


def locate_macos_apps_with_executable_name(name, *args, **kwargs):
    for app_path in locate_macos_apps(*args, **kwargs):
        if os.path.exists(os.path.join(app_path, 'Contents/MacOS', name)):
            yield MacOSApplication(app_path)


def locate_blender_versions_macos(search_paths=['/Applications'], recursion_depth_limit=None):
    # does the user have commandline blender...?
    try:
        subprocess.check_output(['blender', '--version'])
        yield CommandlineBlenderRunner('blender')
    except FileNotFoundError:
        pass

    for app in locate_macos_apps_with_executable_name('blender'):
        yield MacOSBlenderRunner(app)

    # for app_path in locate_macos_apps(search_paths, recursion_depth_limit=recursion_depth_limit):
    #     if os.path.exists(os.path.join(app_path, 'Contents/MacOS/blender')):
    #         yield MacOSBlenderRunner(app_path)


def locate_unity_versions_macos(search_paths=['/Applications'], recursion_depth_limit=None):
    return locate_macos_apps_with_executable_name('Unity')
    # for app_path in locate_macos_apps(search_paths, recursion_depth_limit=recursion_depth_limit):
    #     if os.path.exists(os.path.join(app_path, 'Contents/MacOS/Unity')):
    #         yield MacOSApplication(app_path)


if __name__ == '__main__':
    # apps = list(locate_macos_apps())
    # print("found %d applications:" % len(apps))
    # for app in apps:
    #     print(app)

    for blender in locate_blender_versions_macos():
        print("found blender {version}: {path}".format(version=blender.version(), path=blender.cmd))

    for unity in locate_unity_versions_macos():
        print("found unity {version}: {path}".format(version=unity.version().lower().lstrip('unity version').strip(), path=unity.exec_path))
    # CommandlineBlenderRunner().version()
    # ProgramBlenderRunner('/Applications/Blender/blender.app/Contents/MacOS/blender').version()
    # ProgramBlenderRunner('/Applications/blender-2.80-beta.app/Contents/MacOS/blender').version()
    # ProgramBlenderRunner('/Applications/blender-2.80-beta.app/Contents/MacOS/blender').version()
