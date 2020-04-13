import platform


print(platform.system())
operating_system = platform.system().lower()
if operating_system == 'darwin':
    from blender_utils_macos import get_installed_blender_versions
elif operating_system == 'linux':
    from blender_utils_linux import get_installed_blender_versions
elif operating_system == 'windows':
    from blender_utils_windows import get_installed_blender_versions
else:
    raise Exception("Unimplemented for OS {}".format(operating_system))


if __name__ == '__main__':
    for version, exec_path in get_installed_blender_versions().items():
        print("found blender {version}: {path}".format(version=version,
                                                       path=exec_path))
