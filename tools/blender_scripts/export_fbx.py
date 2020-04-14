import bpy
import sys
import os


def export_fbx(src_file, output=None, global_scale=None, **kwargs):
    print("Exporting '%s' => '%s'" % (src_file, output))
    print("current dir: {}".format(os.getcwd()))
    kwargs = {k: eval(v) for k, v in kwargs.items()}
    # if global_scale is not None:
    #     kwargs['global_scale'] = float(global_scale)
    bpy.ops.export_scene.fbx(
        filepath=output, 
        object_types={'ARMATURE', 'EMPTY', 'MESH'},
        **kwargs)


if __name__ == '__main__':
    # Handle blender .bpy args
    # => assemble virtual sys.argv relative to this script
    blender, src_file = sys.argv[0], sys.argv[1]
    args = []
    src_bpy = None
    for i, arg in enumerate(sys.argv):
        if arg == '--':
            args = sys.argv[i + 1:]
            break
        elif arg.endswith('.py'):
            print(i, arg)
            src_bpy = arg
    argv = [src_bpy, src_file] + args
    script_args = argv[1:]

    # split args, kwargs + use these to call a function
    args, kwargs = [], {}
    while len(script_args) > 0:
        arg = script_args[0]
        if arg.startswith('--') or arg.startswith('-'):
            kwargs[arg.lstrip('-')] = script_args[1]
            script_args = script_args[2:]
        else:
            args.append(arg)
            script_args = script_args[1:]

    # print("got args: {}, {}".format(args, kwargs))
    export_fbx(*args, **kwargs)
