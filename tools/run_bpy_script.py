from apps.find_blender import find_blender
from cache_utils.cache_utils import cache
import subprocess
import sys
import os


BLENDER_VERSION = '2.80'


def get_blender(version=BLENDER_VERSION):
    return cache('blender').cached('blender_path', find_blender, version)


def run_blender_script(script_name, blend_file, *args, **kwargs):
    # if os.path.exists(script_name):
    #     bpy_script = script_name
    # else:
    # get path to `blender_scripts` dir 
    # relative to where this script was invoked
    exec_path = os.path.split(sys.argv[0])[0]
    print("Exec path: {}".format(exec_path))
    scripts_dir = os.path.join(exec_path, 'blender_scripts')
    if not os.path.exists(scripts_dir):
        print("missing (or could not locate) scripts dir! {}".format(scripts_dir))
        return
    bpy_script = os.path.join(scripts_dir, script_name)
    if not os.path.exists(bpy_script):
        print("could not locate bpy script '{}' in '{}'!".format(script_name, scripts_dir))
        files = [file for file in os.listdir(scripts_dir)]
        print("found {} python script(s) instead:".format(len(files)))
        for file in files:
            print(os.path.join(scripts_dir, file))
        return

    cmd = [get_blender(), blend_file, '-b', '-P', bpy_script, '--']
    for k, v in kwargs.items():
        if len(k) == 1:
            cmd += ['-{}'.format(k), str(v)]
        else:
            cmd += ['--{}'.format(k), str(v)]
    cmd += list(map(str, args))
    print(' '.join(cmd))
    result = subprocess.run(cmd)
    print(result)


def export_fbx(input_blend_file, output):
    run_blender_script('export_fbx.py',
        blend_file=input_blend_file,
        output=output,
        global_scale=1e-3)


if __name__ == '__main__':
    # print(get_blender())
    # print(get_blender())
    # print(get_blender())
    # run_blender_script(
    #     bpy_script='blender_scripts/export_fbx.py',
    #     blend_file='../tests/export_fbx/input/test.blend',
    #     output='test.fbx')
    export_fbx(
        '../tests/export_fbx/input/test.blend',
        'test.fbx')