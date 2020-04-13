import subprocess
import re
from macos_utils import locate_macos_apps_with_executable_name


def get_installed_blender_versions():
    def locate_versions():
        try:
            subprocess.check_output(['blender', '--version'])
            info = CommandlineBlenderRunner('blender')
            yield info.version(), info.cmd
        except FileNotFoundError as e:
            print(e)

        for app in locate_macos_apps_with_executable_name('blender'):
            app = MacOSBlenderRunner(app)
            yield app.version(), app.cmd
    return dict(locate_versions())


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


class MacOSBlenderRunner(ProgramBlenderRunner):
    def __init__(self, app):
        self.app = app
        super().__init__(self.app.exec_path)

    def version(self):
        # v1 = super().version()
        v2 = self.app.version()
        return v2


if __name__ == '__main__':
    for version, path in get_installed_blender_versions().items():
        print("found blender '{version}': '{path}'".format(version=version,
                                                       path=path))