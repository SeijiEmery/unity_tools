import platform


# print(platform.system())
operating_system = platform.system().lower()
if operating_system == 'darwin':
    from blender_utils_macos import get_installed_blender_versions
    operating_system_name = 'macos'
elif operating_system == 'linux':
    from blender_utils_linux import get_installed_blender_versions
    operating_system_name = 'linux'
elif operating_system == 'windows':
    from blender_utils_windows import get_installed_blender_versions
    operating_system_name = 'windows'
else:
    raise Exception("Unimplemented for OS {}".format(operating_system))

from blender_utils_web import get_blender_version_download_links


def find_blender(version):
    # TODO: add fuzzy version matching, ie. '>=2.80', '~2.80', '<2.80', etc.
    installed_versions = get_installed_blender_versions()
    if version in installed_versions:
        return installed_versions[version]
    else:
        print("blender version '{}' not found; found {} version(s):".format(version, len(installed_versions)))
        for v, path in installed_versions.items():
            print("    {}: {}".format(v, path))
        print("searching web archive...")
        versions = get_blender_version_download_links(version, operating_system_name)
        print("found {} download(s) for blender version '{}', platform '{}':".format(len(versions), version, operating_system_name))
        for url in versions:
            print("    {}".format(url))


if __name__ == '__main__':
    for version, exec_path in get_installed_blender_versions().items():
        print("found blender {version}: {path}".format(version=version,
                                                       path=exec_path))
    blender = find_blender('2.80')
    if blender:
        print("Found blender: '{}'".format(blender))
    else:
        print("No matching blender version installed :(")
