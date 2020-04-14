from apps.find_blender import find_blender
from cache_utils.cache_utils import cache


BLENDER_VERSION = '2.80'


def get_blender(version=BLENDER_VERSION):
    return cache('blender').cached('blender_path', find_blender, version)


if __name__ == '__main__':
    print(get_blender())
    print(get_blender())
    print(get_blender())
