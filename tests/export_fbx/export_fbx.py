import subprocess
import os


def run_bpy_script(file, script, args):
    args = args.split() if type(args) != list else args
    script = os.path.join('../../tools/blender_scripts', script)
    args = ['blender', file, '--background', '--python', script] + args
    print("Running '%s'" % ' '.join(args))
    subprocess.run(args)


if __name__ == '__main__':
    run_bpy_script('input/test.blend', 'export_fbx.py', 'output')
