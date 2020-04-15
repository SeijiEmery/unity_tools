import os
import re
import yaml


class UnityFile:
    def __init__(self, path, data=None, asset=None):
        self.path = path
        self.data = data
        self.error = None
        self.asset = asset

    @property
    def exists(self):
        return os.path.exists(self.path)

    @property
    def is_loaded(self):
        return self.data is not None

    @property
    def has_error(self):
        return self.error is not None

    def load(self):
        self.error = None
        try:
            with open(self.path, 'r') as f:
                self.data = f.read()
        except IOError as e:
            self.error = e
        return self


class UnityYamlFile(UnityFile):
    def __init__(self, *args, **kwargs):
        super(UnityFile, self).__init__(*args, **kwargs)

    def load(self):
        super().load()
        if self.error is None:
            try:
                self.data = yaml.load(self.data, Loader=yaml.CBaseLoader)
                # print("Loaded '%s' => yaml with keys %s" % (self.path, self.data.keys()))
            except yaml.YAMLError as e:
                self.error = e
        return self


class UnityMetaFile(UnityYamlFile):
    def __init__(self, *args, **kwargs):
        super(UnityYamlFile, self).__init__(*args, **kwargs)
        self.guid = None

    def load(self):
        super().load()
        if self.error is None:
            if 'guid' not in self.data:
                self.error = Exception("No 'guid' field in data (keys: '%s')\n\t%s" % (
                    self.data.keys(), self.data))
                self.guid = None
            else:
                self.guid = self.data['guid']
        return self


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


def read_yaml(data, loader=yaml.CBaseLoader):
    try:
        data = yaml.load(data, Loader=loader)
        return None, data
    except yaml.YAMLError as e:
        return e, data


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
        for key, value in data.items():
            object_name, data = key, value
        if type(data) != dict:
            return Exception("Invalid object data format (expected nested element to be dict, got %s): %s"
                             % (type(data), data)), content
        objects[object_id] = {
            'type': object_name,
            'typeid': object_type,
            'data': data
        }
    return None, objects


class UnitySceneDataFile(UnityFile):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load(self):
        super().load()
        if self.error is None:
            self.error, self.data = read_unity_yaml_objects(self.data)
        return self


class UnityAsset:
    def __init__(self, asset_type, path, guid=None):
        self.asset_type = asset_type
        self.path = path
        self.meta_path = path + '.meta'
        self.file = UnityFile(self.path, asset=self)
        self.metafile = UnityMetaFile(self.meta_path, asset=self)
        self.guid = guid or self.metafile.guid
        self.db = None

    def load_metafile(self):
        self.metafile.load()
        self.guid = self.metafile.guid


class UnityDirectoryAsset(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(UnityDirectoryAsset, path, *args, **kwargs)


class UnityFileRef:
    def __init__(self, guid, fileid):
        self.id = int(fileid)
        self.guid = guid if self.id != 0 else None

    @property
    def uuid(self):
        return (self.guid, self.id)

    @property
    def empty(self):
        return self.id == 0

    def __cmp__(self, other):
        return cmp(self.uuid, other.uuid)

    def __repr__(self):
        if self.empty:
            return "null"
        return "&{}:{:d}".format(self.guid, self.id)


class UnityType:
    def __init__(self, name, typeid):
        self.name = name
        self.typeid = int(typeid)

    def __cmp__(self, other):
        if type(other) != UnityType:
            return cmp(type(self), type(other))
        return cmp((self.name, self.typeid), (other.name, other.typeid))

    def __repr__(self):
        return '{}!{:d}'.format(self.name, self.typeid)


def fmt_prop(name, value):
    if value is None:
        return "{name}: null".format(name=name)
    elif type(value) == UnityFileRef:
        return "{name}: {value}".format(name=name, value=value)
    return "{name}: {type} {value}".format(
        name=name, value=value, type=type(value).__name__)


def list_flat_properties(props):
    def dump_props(props, name_prefix):
        if type(props) == dict:
            for k, v in props.items():
                for result in dump_props(v, "{}.{}".format(name_prefix, k)):
                    yield result
        elif type(props) == list:
            for i, v in enumerate(props):
                for result in dump_props(v, "{}[{:d}]".format(name_prefix, i)):
                    yield result
        else:
            yield name_prefix, props
    if type(props) != dict:
        raise Exception(
            "properties must be a dictionary, got {}!".format(type(props)))
    for k, v in props.items():
        for result in dump_props(v, k):
            yield result


class UnitySceneGraphObject:
    def __init__(self, asset, ref, object_type, properties):
        self.asset = asset
        self.ref = ref
        self.type = object_type
        self.properties = properties
        self._flat_properties = None

    @property
    def flat_properties(self):
        if self._flat_properties is None:
            self._flat_properties = dict(list_flat_properties(self.properties))
        return self._flat_properties

    def __repr__(self):
        return "{type} {ref} {path}\n{properties}".format(
            type=self.type,
            ref=self.ref,
            path=self.asset.path if self.asset else '',
            properties='\n'.join([
                '  %s' % fmt_prop(name, value)
                for name, value in self.flat_properties.items()
            ])
        )


class UnityAssetSceneGraph(UnityAsset):
    def __init__(self, asset_type, path, *args, **kwargs):
        super(UnityAsset, self).__init__(asset_type, path, *args, **kwargs)
        self.objects = None

    def load(self):
        self.file.__class__ = UnitySceneDataFile
        self.file.load()
        guid = self.guid

        def parse_file_ref(info):
            ref_id = info['fileID']
            ref_guid = info['guid'] if 'guid' in info else None
            if 'type' not in info:
                return UnityFileRef(ref_guid or guid, int(ref_id))
            t = int(info['type'])
            if t == 2:
                return UnityFileRef(ref_guid, int(ref_id))
            else:
                return info

        def parse_properties(data):
            if type(data) == str:
                if data.isnumeric():
                    if '.' in data:
                        return float(data)
                    else:
                        return int(data)
                else:
                    return data
            elif type(data) == list:
                return list(map(parse_properties, data))
            elif type(data) == dict:
                if 'fileID' in data:
                    return parse_file_ref(data)
                else:
                    return {k: parse_properties(v) for k, v in data.items()}
            else:
                raise Exception(
                    "Unhandled type {}: {}".format(type(data), data))

        self.objects = {
            int(ref_id): UnitySceneGraphObject(
                asset=self,
                ref=UnityFileRef(guid=guid, fileid=ref_id),
                object_type=UnityType(name=obj['type'], typeid=obj['typeid']),
                properties=parse_properties(obj['data'])
            )
            for ref_id, obj in self.file.data.items()
        }

    def __repr__(self):
        if self.objects:
            objects = ''.join([
                '\n  %s' % str(obj).replace('\n', '\n  ')
                for obj in self.objects.values()
            ])
        else:
            objects = ''
        if not self.objects:
            return "file &{guid}: {path}".format(
                guid=self.guid,
                path=self.path)
        return "file &{guid}: {path}{objects}".format(
            guid=self.guid,
            path=self.path,
            objects=objects)


class UnityAssetPrefab(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super(UnityAssetSceneGraph, self).__init__(
            UnityAssetPrefab, path, *args, **kwargs)


class UnityAssetScene(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super(UnityAssetSceneGraph, self).__init__(
            UnityAssetScene, path, *args, **kwargs)


class UnityAssetMaterial(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super(UnityAssetSceneGraph, self).__init__(
            UnityAssetMaterial, path, *args, **kwargs)


class UnityAssetCSharpScript(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(UnityAssetCSharpScript, path, *args, **kwargs)


UNITY_ASSET_EXT_TYPES = {
    '.prefab': UnityAssetPrefab,
    '.unity': UnityAssetScene,
    '.mat': UnityAssetMaterial,
    '.cs': UnityAssetCSharpScript,
}
UNITY_ASSET_EXTS = \
    {k for k in UNITY_ASSET_EXT_TYPES.keys()} | \
    {'%s.meta' % k for k in UNITY_ASSET_EXT_TYPES.keys()} | \
    {'.meta'}


class UnityAssetDB:
    """ Rough encapsulation of the unity asset system """

    def __init__(self, root_dir, logger=None):
        self.root_dir = root_dir
        self.files = {}
        self.assets_by_path = {}
        self.assets_by_guid = {}
        self.removed_assets = {}
        self.transaction_log = []
        self.logger = logger

    def add_file(self, file):
        """ Inserts a tracked file into the db """
        if file is not None:
            file.db = self
            self.files[file.path] = file
            if self.logger:
                self.logger.added_file(file)

    def remove_file(self, file):
        """ Removes a tracked file from the db """
        if file is not None:
            self.db = None
            del self.files[file.path]
            if self.logger:
                self.logger.removed_file(file)

    def add_asset(self, asset):
        """ Inserts or updates a tracked asset into the db """
        asset.db = self
        self.assets_by_path[asset.path] = asset
        self.assets_by_guid[asset.guid] = asset
        self.add_file(asset.file)
        self.add_file(asset.metafile)
        if self.logger:
            self.logger.updated_asset(asset)

    def update_asset(self, asset):
        self.add_asset(asset)

    def remove_asset(self, asset):
        """ Removes a tracked asset from the db """
        asset.db = None
        del self.assets_by_path[asset.path]
        del self.assets_by_guid[asset.guid]
        self.remove_file(asset.file)
        self.remove_file(asset.metafile)
        if self.logger:
            self.logger.removed_asset(asset)

    def has_matching_file(self, path):
        return path in self.files

    def load_missing_metafiles(self):
        assets_missing_metafiles = [
            (path, asset) for path, asset in self.assets_by_path.items()
            if not asset.metafile.is_loaded
        ]
        import multiprocessing as mp
        pool = mp.Pool(16)
        results = pool.map(load_metafile, assets_missing_metafiles)
        for path, asset in results:
            self.update_asset(asset)


def load_metafile(args):
    path, asset = args
    asset.load_metafile()
    return path, asset


def split_file_path_name_ext(path):
    base_path, file_name = os.path.split(path)
    ext_parts = file_name.split('.')
    if len(ext_parts) > 1:
        return base_path, ext_parts[0], '.' + '.'.join(ext_parts[1:])
    return base_path, ext_parts[0], ''


class EmptyTransactionLogger:
    def __init__(self):
        pass


class UnityFileSystemResponder:
    def __init__(self, db, transaction_logger=None):
        self.db = db
        self.transactions = transaction_logger or EmptyTransactionLogger()

    def add_file(self, path):
        original_path = path
        base_path, file, ext = split_file_path_name_ext(path)
        print("'%s' '%s' '%s'" % (base_path, file, ext))

        # ignore files we don't care about
        if ext not in UNITY_ASSET_EXTS:
            print("skipping %s with ext '%s' (not in %s)" %
                  (path, ext, UNITY_ASSET_EXTS))
            return

        # skip files that we're alread tracking
        if self.db.has_matching_file(path):
            return

        # get path to asset file (.meta file is implicit)
        if ext.endswith('.meta'):
            ext = ext[:-5]
        path = os.path.join(base_path, file + ext)

        # check if meta file references a directory
        if ext == '' and os.path.isdir(path):
            return self.add_dir(path)
        elif ext not in UNITY_ASSET_EXT_TYPES:
            return
            # raise Exception("Missing handler for extension '%s' for file at path '%s' (original path '%s') in %s" % (
            #     ext, path, original_path, UNITY_ASSET_EXT_TYPES))

        # scan asset + add to db
        self.db.add_asset(UNITY_ASSET_EXT_TYPES[ext](path))

    def add_dir(self, path):
        if not os.path.isdir(path):
            raise Exception("'{}' is not a directory!".format(path))

        self.db.add_asset(UnityDirectoryAsset(path))

    def scan_all(self):
        root_dir = self.db.root_dir
        for path, dirs, files in os.walk(root_dir):
            for file in files:
                self.add_file(os.path.join(path, file))
            for dir in dirs:
                self.add_dir(os.path.join(path, dir))
        self.db.load_missing_metafiles()


if __name__ == '__main__':
    class Logger:
        def added_file(self, file):
            pass
            # print("Added file: '%s'" % file.path)

        def removed_file(self, file):
            pass
            # print("Removed file: '%s'" % file.path)

        def updated_asset(self, asset):
            pass
            # if asset.asset_type != UnityDirectoryAsset:
            #     print("updated asset: '%s'" % asset.path)

        def removed_asset(self, asset):
            print("removed asset: '%s'" % asset.path)

    import sys
    root_dir = sys.argv[1] if len(
        sys.argv) > 1 else '/Users/semery/projects/glitch-escape/Assets/'
    db = UnityAssetDB(root_dir, logger=Logger())
    scanner = UnityFileSystemResponder(db)
    scanner.scan_all()
    assets = {asset for asset in db.assets_by_path.values(
    ) if asset.asset_type != UnityDirectoryAsset}
    # for asset in assets:
    #     print("%s: %s" % (asset.guid, asset.path))
    # print("%d asset(s)" % len(assets))

    ASSET = "/Users/semery/projects/glitch-escape/Assets/GlitchEscape/Cutscenes/Cutscenes.prefab"
    print(ASSET)
    asset = db.assets_by_path[ASSET]
    asset.load()
    print(asset)
