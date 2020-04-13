import bpy
import argparse

parser = argparse.ArgumentParser(description="Export a .blend file into a .fbx file + textures")
parser.add_argument('input_file', type=str,
    help='path to input .blend file')
parser.add_argument('output_file', type=str,
    help='path to output .fbx file')
args = parser.parse_args()
print(args)



