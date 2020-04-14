import bpy
import sys
import os


def print_material_connections(node, indent):
    if not node:
        return
    for output_node in node.outputs:
        for link in output_node.links:
            if link.to_node:
                print("{indent}{} '{}' {} as {} {}\n{indent}  -> linked to {} '{}' {} as {} {}".format(
                    node.type, node.name, node,
                    link.from_socket.type, link.from_socket,
                    link.to_node.type, link.to_node.name,
                    link.to_node, link.to_socket.type, link.to_socket,
                    indent='  '*indent))
                print_material_connections(link.to_node, indent=indent+1)


def _export_textures(export_dir):
    """ Export all textures in this scene """
    # https://devtalk.blender.org/t/how-to-get-all-textures-in-2-80/5205
    textures = set()
    print()
    for obj in bpy.data.objects:
        print("object '{}':".format(obj.name))
        for mat_slot in obj.material_slots:
            for node in mat_slot.material.node_tree.nodes:

                # TODO: figure out how to export materials...
                # print("{} node: {}".format(node.type, node))
                # print("{}".format(node.inputs))
                # print("{}".format(node.outputs))
                # print("{}".format(node.id_data))

                # save textures
                if node.type == 'TEX_IMAGE':
                    textures.add(node)
                    print("  Texture '{}':".format(node.image.name))
                    print_material_connections(node, indent=2)
        print()

    if textures:
        texture_dir = os.path.join(export_dir, 'Textures')
        if not os.path.exists(texture_dir):
            os.makedirs(texture_dir)
        for texture in textures:
            name = texture.image.name
            # convert garbage blend names like 'foo.png.001' => 'foo.001.png'
            if '.png' in name and not name.endswith('.png'):
                name = ''.join(name.split('.png')) + '.png'
            # save texture
            image_path = os.path.join(texture_dir, name)
            print("Saving '{}'".format(image_path))
            texture.image.save_render(image_path)


def _export_fbx(export_file, **kwargs):
    typed_args = {
        'global_scale': float
    }
    for x, t in typed_args.items():
        if x in kwargs:
            kwargs[x] = t(kwargs[x])
    bpy.ops.export_scene.fbx(
        filepath=export_file,
        object_types={'ARMATURE', 'EMPTY', 'MESH'},
        embed_textures=False,
        **kwargs)


def export_fbx(src_file, output=None, **kwargs):
    src_dir, src_file_name = os.path.split(src_file)
    if output is None:
        export_dir = src_dir
        export_path = src_file.replace('.blend', '.fbx')
    elif os.path.isdir(output):
        export_dir = output
        export_file = os.path.join(export_dir, src_file_name.replace('.blend', '.fbx'))
    else:
        export_dir = os.path.split(output)[0]
        if export_dir and not os.path.exists(export_dir):
            os.makedirs(export_dir)
        export_file = output

    print("Exporting '%s' => '%s'" % (src_file, output))
    print("current dir: {}".format(os.getcwd()))
    kwargs = {k: eval(v) for k, v in kwargs.items()}

    _export_textures(export_dir)
    # _export_fbx(export_file)


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
