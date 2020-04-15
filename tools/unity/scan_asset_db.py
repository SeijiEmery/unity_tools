#!/usr/bin/env python3
import os
import sys
import yaml
import multiprocessing as mp
import re


def get_file_name_and_base_extension(file_name):
    parts = file_name.split('.')
    name = parts[0]
    ext = '.' + '.'.join(parts[1:]) if len(parts) > 1 else ''
    base_ext = ext.rstrip('.meta')
    return name, base_ext


def list_assets_and_metafiles(base_dir, asset_ext_types):
    asset_ext_types = set(asset_ext_types)
    visited = set()
    for path, dirs, files in os.walk(base_dir):
        for file in files:
            name, ext = get_file_name_and_base_extension(file)
            base_path = os.path.join(path, name)
            asset_path = '%s.%s' % (base_path, ext)
            if asset_path not in visited:
                meta_path = '%s.%s.meta' % (base_path, ext)
                yield asset_path, meta_path, ext
        for dir in dirs:
            dir_asset_path = os.path.join(path, dir)
            if dir_asset_path not in visited:
                meta_path = dir_asset_path + '.meta'
                yield dir_asset_path, meta_path, ''


def list_files(base_dir='.'):
    asset_loader_types = {
        '': (None, Directory),
        '.prefab': ('yaml', UnityPrefabFile),
        '.unity': ('yaml', UnitySceneFile),
        '.mat': ('yaml', UnityMaterialFile),
        '.cs': ('text', UnityCSharpScript),
    }
    visited = set()
    for asset_path, meta_path, ext in list_assets_and_metafiles(base_dir, asset_loader_types.keys()):
        if not os.path.exists(meta_path):
            print("missing meta file for asset %s" % asset_path)
            continue
        if not os.path.exists(asset_path):
            print("missing asset file for meta file %s" % meta_path)
            continue
        yield asset_path, meta_path, asset_loader_types[ext]

    # for path, dirs, files in os.walk(base_dir):
    #     for file in files:
    #         name, ext = get_file_name_and_base_extension(file)
    #         ext = '.'.join(file.split('.')[1:])
    #         if ext != '':
    #             ext = '.' + ext.rstrip('.meta')
    #         if ext not in asset_loader_types:
    #             # print("skipping asset '%s' '%s' of type '%s'" % (path, file, ext))
    #             continue
    #         name = file.split('.')[0]
    #         asset_name = name + ext
    #         asset_path = os.path.join(path, asset_name)
    #         if asset_path not in visited:
    #             # if ext != '':
    #             # print("scanning asset: '%s' '%s' '%s' (file '%s')" % (path, name, ext, file))
    #             visited.add(asset_name)
    #             meta_name = asset_name+'.meta'
    #             meta_path = os.path.join(path, meta_name)
    #             asset_path = os.path.join(path, asset_name)
    #             if not os.path.exists(meta_path):
    #                 print("missing meta file for asset %s" % asset_path)
    #                 continue
    #             if not os.path.exists(asset_path):
    #                 print("missing asset file for meta file %s" % meta_path)
    #                 continue
    #             yield name, asset_name, asset_path, meta_path, asset_loader_types[ext]


def _load_file(packed_args):
    file, loader = packed_args[0], packed_args[1]
    args = packed_args[2] if len(packed_args) > 2 else []
    kwargs = packed_args[3] if len(packed_args) > 3 else {}
    try:
        error, result = loader(file, *args, **kwargs)
        return file, error, result
    except IOError as e:
        return file, e, None
    except Exception as e:
        return file, e, None


def bulk_load_files(generator, error_handler, parallel=True, pool=None, *args, **kwargs):
    if parallel and pool is None:
        pool = mp.Pool(MP_POOL_THREADS)
    if parallel:
        results = pool.map(_load_file, generator(*args, **kwargs))
    else:
        results = map(_load_file, generator(*args, **kwargs))
    if error_handler is not None:
        for file, error, result in results:
            if error is not None:
                error_handler(file, error, result)
            else:
                yield result
    else:
        for error, result in results:
            if error is None:
                yield result


def bulk_load_call(fcn, file, *args, **kwargs):
    return (file, fcn, args, kwargs)


def load_yaml(file, loader=yaml.CBaseLoader, multiple_documents=False, preprocessor=None):
    try:
        with open(file, 'r') as f:
            if preprocessor is not None:
                f = preprocessor(f.read())
            if multiple_documents:
                data = yaml.loadall(f, loader=loader)
            else:
                data = yaml.load(f, loader=loader)
        return None, data
    except IOError as e:
        return e, None
    except yaml.YAMLError as e:
        return e, None


def load_meta_file_guid(file):
    error, data = load_yaml(file)
    if error is not None:
        if 'guid' in data:
            data = {'guid': data['guid']}
        else:
            error = Exception("meta file '%s' missing guid! %s" % (file, data))
    return error, data


def load_text(file):
    try:
        data = None
        with open(file, 'r') as f:
            data = f.read()
            error = None
    except IOError as e:
        error = e
    return error, data


def read_yaml(data, loader=yaml.CBaseLoader):
    try:
        data = yaml.load(data, loader=loader)
        return None, data
    except yaml.YAMLError as e:
        return e, data


def find_unity_yaml_objects(content):
    """ Locates all unity .yaml objects within a unity .yaml file.

    Generates a list of tuples (object_type, object_id, yaml_content)
    for each sub-document found in this file.

    Uses regexes to locate sub-documents (and handle !u!<tag> &<id> syntax),
    which is simpler than fully supporting unity's full tag spec +
    serialization format.

    Used to implement read_unity_yaml_objects(content)
    """
    regex = re.compile(r'---\s+!u!(\d+)\s+&(\d+)[^\n]+\n')
    prev_match = None
    while True:
        match = re.search(regex, content)
        if prev_match is not None:
            object_type, object_id = prev_match.group(1, 2)
            if match is not None:
                yield object_type, object_id, content[:match.start()]
            else:
                yield object_type, object_id, content
                return
        elif match is None:
            return
        if match is not None:
            content = content[match.end():]
        prev_match = match


def read_unity_yaml_objects(content):
    """ Reads in / parses all objects from a unity .yaml file (as a string).

    Returns a dictionary of objects with the following format:
        guid: int => { type: str, typeid: int, data: dict }

    Follows the non-throwing `return error, data`, where:
        error: None (success), or an exception (parsing error / invalid format)
        data:  the dictionary above (iff successful)

    Implemented using find_unity_yaml_objects and the pyYAML library
    (using C backend for speed); called by load_unity_yaml_objects(<filepath>)
    """
    objects = {}
    for object_type, object_id, content in find_unity_yaml_objects(content):
        error, data = read_yaml(content)
        if error is not None:
            return error, content
        if type(data) != dict:
            return Exception("Invalid object data format! %s: %s"
                             % (type(data), data)), content
        if len(data) != 1:
            return Exception("Invalid object data (expected 1 object, got %d): %s"
                             % (len(data), data)), content
        for key, value in object_data:
            object_name, object_data = key, value
        if type(object_data) != dict:
            return Exception("Invalid object data format (expected nested element to be dict, got %s): %s"
                             % (type(object_data), object_data)), content
        objects[object_id] = {
            'type': object_name,
            'typeid': object_type,
            'data': object_data
        }
    return None, objects


def load_unity_yaml_objects(file):
    """ Loads .yaml objects from a unity .yaml file from a given file path.

    Implemented using read_unity_yaml_objects() + load_text()

    Follows the non-throwing `return error, data` format, where:
        error: None (success), or an exception (file read error, parsing error,
            or invalid format)
        data: a dictionary of objects returned from read_unity_yaml_objects
            (if successful), or additional error context (if failed)
    """

    error, data = load_text(file)
    if error is not None:
        return error, data
    return read_unity_yaml_objects(data)


def load_unity_scene_file(file):
    error, data = load_unity_yaml_objects(file)
    if error is not None:
        pass
    return error, data


def load_unity_prefab_file(file):
    error, data = load_unity_yaml_objects(file)
    if error is not None:
        pass
    return error, data


def load_unity_material_file(file):
    error, data = load_yaml(file, multiple_documents=True)
    if error is not None:
        pass
    return error, data


def load_directory_info(directory):
    error, data = None, None
    return error, data


def scan_files(base_dir='.', parallel=True):
    meta_file_loaders = {
        '': load_meta_file_guid,
        '.unity': load_meta_file_guid,
        '.prefab': load_meta_file_guid,
        '.cs': load_meta_file_guid,
        '.mat': load_meta_file_guid,
    }
    asset_loaders = {
        '': load_directory_info,
        '.unity': load_unity_scene_file,
        '.prefab': load_unity_prefab_file,
        '.mat': load_unity_material_file,
    }

    def generate_file_load_jobs():
        for asset_path, meta_path, ext in list_files(base_dir):
            yield bulk_load_call(meta_file_loaders[ext], meta_path)
            if ext in asset_loaders:
                yield bulk_load_call(asset_loaders[ext], asset_path)

    def handle_file_load_error(file, error, result):
        if result is not None:
            print("file read on '%s' failed!\n\t%s\n%s" %
                  (path, error, result))
        else:
            print("file read on '%s' failed!\n\t%s" % (path, error))

    def load_all_assets():
        asset_files = {}
        meta_files = {}
        asset_list = set()

        # bulk load all asset + metafile data
        results = bulk_load_files(
            generator=generate_file_load_jobs,
            error_handler=handle_file_load_error,
            parallel=parallel,
            pool=None
        )
        for file, data in results:
            if file.endswith('.meta'):
                file = file.rstrip('.meta')
                if file in meta_files:
                    print("Already processed meta file '%s.meta'!" % file)
                meta_files[file] = data
            else:
                if file in asset_files:
                    print("Already processed asset file '%s'!" % file)
                asset_files[file] = data
            asset_list.add(file)

        assets_by_guid = {}
        for asset_path in asset_list:
            if asset_path not in asset_files:
                print("Missing asset file for '%s.meta'! skipping" % asset_path)
                continue
            if asset_path not in meta_files:
                print("Missing meta file for '%s'! skipping" % asset_path)
                continue

            asset, metafile = asset_files[asset_path], meta_files[asset_path]
            if 'guid' not in metafile:
                print("Metafile '%s.meta' missing guid! (contents: %s)" %
                      (asset_path, metafile))
                continue
            guid = metafile['guid']
            asset['guid'] = guid
            asset['meta'] = metafile
            assets_by_guid[guid] = asset
        return assets_by_guid

    def resolve_asset_references(assets):
        return assets

    assets = load_all_assets()
    assets = resolve_asset_references(assets)
    return assets


def _read_yaml(content):
    content = re.sub(r'%TAG !u! [^\n]+\n', '---\n', content)
    content = re.sub(r'--- !u!\d+ &(\d+)\s+(?:stripped\s+)?(\w+):',
                     r'\2:\n  fileId: \1', content)
    # print(content)
    return list(yaml.load_all(content, Loader=yaml.CBaseLoader))


def read_yaml_or_text_file(file_id, path, load_type):
    if load_type not in ('yaml', 'text'):
        return file_id, load_type, path, None, None
    try:
        with open(path, 'r') as f:
            data = f.read()
            if load_type == 'text':
                return file_id, load_type, path, None, data
            try:
                data = _read_yaml(data)
                return file_id, load_type, path, None, data
            except yaml.YAMLError as e:
                try:
                    data = f.read()
                except IOError:
                    data = None
                return file_id, load_type, path, e, data
    except IOError:
        return file_id, load_type, path, e, None


MP_POOL_THREADS = 32


def scan_files(base_dir='.'):
    read_file_jobs = []
    file_list = list(list_files())
    # file_list = file_list[:10]

    for _, asset_name, asset_path, meta_path, loader in file_list:
        # read meta file
        read_file_jobs.append((asset_path, meta_path, 'yaml'))
        loader_type, _ = loader
        if loader_type in ('yaml', 'text'):
            # read asset file (yaml or text)
            read_file_jobs.append((asset_path, asset_path, loader_type))

    # do bulk file reads on N threads
    pool = mp.Pool(MP_POOL_THREADS)
    file_data = pool.map(read_yaml_or_text_file, read_file_jobs)

    # assign data + check for errors:
    asset_data = {}
    asset_metadata = {}

    for target_file, file_type, path, error, payload in file_data:
        if error is not None:
            print("%s file read on '%s' failed!\n\t%s\n%s" %
                  (file_type, path, error, payload))
        else:
            if path.endswith('.meta'):
                asset_metadata[target_file] = payload
            else:
                asset_data[target_file] = payload

    fs = FileSystem()
    for _, asset_name, asset_path, meta_path, loader in file_list:
        if asset_path not in asset_metadata:
            print("missing metadata for %s, skipping" % asset_path)
            continue

        loader_type, loader_type = loader
        if loader_type is None:
            data = None
        elif asset_path not in asset_data:
            print("missing data for '%s' (file read failed?), skipping" %
                  asset_path)
            continue
        else:
            data = asset_data[asset_path]

        metadata = asset_metadata[asset_path]
        # print(metadata)
        guid = metadata[0]['guid']
        fs.add_file(loader_type(guid, asset_path, asset_name, data, metadata))

    # fs.load_refs()
    return fs


class FileSystem:
    def __init__(self):
        self.files_by_path = {}
        self.files_by_giud = {}
        self.files_by_name = {}
        self.all_files = set()

    def add_file(self, file):
        self.files_by_path[file.path] = file
        self.files_by_giud[file.guid] = file
        self.files_by_name[file.name] = file
        self.all_files.add(file)
        file.fs = self

    def __getitem__(self, name):
        if name in self.files_by_giud:
            return self.files_by_giud[name]
        if name in self.files_by_name:
            return self.files_by_name[name]
        if name in self.files_by_path:
            return self.files_by_path[name]
        return name

    def __repr__(self):
        return '%d file(s):\n' % len(self.all_files) + '\n'.join([
            '%s %s %s' % (file.guid, file.file_type, file.path)
            for file in self.all_files
        ])


class File:
    def __init__(self, guid, path, name, file_type, data, metadata):
        self.guid = guid
        self.path = path
        self.name = name
        self.file_type = file_type
        self.data = data
        self.metadata = metadata
        self.fs = None

    def __cmp__(self, other):
        return cmp(self.path, other.path)


class Directory (File):
    def __init__(self, guid, path, name, data, metadata):
        super().__init__(guid, path, name, 'directory', data, metadata)


class UnitySceneEntity:
    def __init__(self, scene, entity_type, fileid, data):
        self.scene = scene
        self.entity_type = entity_type
        self.id = fileid
        self.data = data

    def locate(self, id, scene_guid=None):
        return self.scene.locate(id, scene_guid)

    def __repr__(self):
        return '%s %s:%s' % (self.entity_type, self.scene.guid, self.id)


class ComponentRef:
    def __init__(self, gameobject, scene, id, owner_guid):
        self.gameobject = gameobject
        self.scene = scene
        self.id = id
        self.owner_guid = owner_guid
        self.broken_reference = False

    def locate(self):
        owning_scene = self.scene.locate_scene(self.owner_guid)
        if not owning_scene:
            self.broken_reference = True
            return self
        component = owning_scene[self.id]
        if component is None:
            self.broken_reference = True
            return self

        self.broken_reference = False

        # update owning gameobject's component ref, if it still points to this
        for i, v in enumerate(self.gameobject.components):
            if v.id == self.id:
                self.gameobject.components[i] = component
                break
        return component

    def __repr__(self):
        if self.broken_reference:
            return '%s:%s (broken reference)' % (self.owner_guid, self.id)
        return self.locate().__repr__()

    def __getattr__(self, attrib):
        if self.broken_reference:
            return None
        return self.locate().__getattr__(self, attrib)


class Component (UnitySceneEntity):
    def __init__(self, *args):
        super().__init__(*args)


def locate_component(gameobject, scene, id, external_scene_guid=None):
    if external_scene_guid is not None:
        owner = scene.locate(external_scene_guid)
        if owner is None:
            return ComponentRef(gameobject, scene, id, external_scene_guid)
    else:
        owner = scene

    component = owner[id]
    if component is None:
        return ComponentRef(gameobject, scene, id, external_scene_guid)
    return component


class GameObject (UnitySceneEntity):
    def __init__(self, *args):
        super().__init__(*args)
        # print(self.data['m_Component'])

        self.components = [
            locate_component(self, self.scene, c['component']['fileID'],
                             c['component']['guid'] if 'guid' in c['component'] else None)
            for c in self.data['m_Component']
        ] if 'm_Component' in self.data else []

    def __repr__(self):
        return super().__repr__() + '\n  components:\n    ' + '\n    '.join(map(str, self.components))


def make_entity(scene, entity_type, *args):
    constructors = {
        'gameobject': GameObject
    }
    t = entity_type.lower()
    if t in constructors:
        return constructors[t](scene, entity_type, *args)
    return UnitySceneEntity(scene, entity_type, *args)


class UnitySceneDataFile (File):
    def __init__(self, *args):
        super().__init__(*args)
        self.entities = {}
        # print('%s %s %s' % (self.guid, self.file_type, self.path))
        for items in self.data:
            for entity_type, data in items.items():
                fileid = data['fileId']
                self.entities[fileid] = make_entity(
                    self, entity_type, fileid, data)
                print(self.entities[fileid])

    def locate_scene(self, scene_guid):
        return self.fs[scene_guid] if self.fs else None

    def locate(self, id, scene_guid=None):
        if scene_guid:
            scene = self.locate_scene(scene_guid)
            if scene is not None:
                return scene[id]
        return self[id]

    def __getitem__(self, id):
        if id in self.entities:
            return self.entities[id]
        return None

    def __repr__(self):
        return '%s %s %s\n' % (self.file_type, self.path, self.guid) + '\n'.join([
            '  %s' % str(entity).replace('\n', '\n  ') for entity in self.entities
        ])


class UnityPrefabFile (UnitySceneDataFile):
    def __init__(self, guid, path, name, data, metadata):
        super().__init__(guid, path, name, 'prefab', data, metadata)


class UnitySceneFile (UnitySceneDataFile):
    def __init__(self, guid, path, name, data, metadata):
        super().__init__(guid, path, name, 'scene', data, metadata)


class UnityCSharpScript (File):
    def __init__(self, guid, path, name, data, metadata):
        super().__init__(guid, path, name, 'c# file', data, metadata)


class UnityMaterialFile (File):
    def __init__(self, guid, path, name, data, metadata):
        super().__init__(guid, path, name, 'material', data, metadata)


if __name__ == '__main__':
    base_dir = sys.argv[1]
    fs = scan_files(base_dir)
    print(fs)
