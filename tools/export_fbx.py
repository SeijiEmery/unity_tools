#!/usr/bin/env python3
import os
import sys
from run_bpy_script import run_blender_script


def export_fbx(input_blend_file, output=None, **kwargs):
    run_blender_script('export_fbx.py',
        blend_file=input_blend_file,
        output=output,
        global_scale=1e-3,
        **kwargs)


if __name__ == '__main__':
    # split args, kwargs + use these to call a function
    script_args = sys.argv[1:]
    args, kwargs = [], {}
    while len(script_args) > 0:
        arg = script_args[0]
        if arg.startswith('--') or arg.startswith('-'):
            kwargs[arg.lstrip('-')] = script_args[1]
            script_args = script_args[2:]
        else:
            args.append(arg)
            script_args = script_args[1:]

    print(args)
    print(kwargs)

    # export_fbx('../tests/export_fbx/input/test.blend', 'test.fbx')
    export_fbx(*args, **kwargs)
