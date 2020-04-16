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
    regex = re.compile(r'---\s+!u!(\d+)\s+&(\d+)[^\n]*\n')
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
    def __init__(self, asset_type, path, loadable=False, guid=None):
        self.asset_type = asset_type
        self.path = path
        self.meta_path = path + '.meta'
        self.file = UnityFile(self.path, asset=self)
        self.metafile = UnityMetaFile(self.meta_path, asset=self)
        self.guid = guid or self.metafile.guid
        self.db = None
        self.loadable = loadable

    def load_metafile(self):
        self.metafile.load()
        self.guid = self.metafile.guid

    def __repr__(self):
        return ("{asset_type} {guid} needs load? {needs_load} loaded? {loaded}" +
                "\n  file {file_path} exists? {file_exists}" +
                "\n  meta {metafile_path} exists? {metafile_exists}"
                ).format(
                    asset_type=type(self).__name__,
                    guid=self.guid,
                    needs_load=self.loadable,
                    loaded=(self.is_loaded
                            if self.loadable
                            else True),
                    file_path=self.file.path,
                    file_exists=self.file.exists,
                    metafile_path=self.metafile.path,
                    metafile_exists=self.metafile.exists)

    def find_object_by_id(self, id):
        return None


class IgnoredAsset(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(IgnoredAsset, path, *args, **kwargs)


class UnityDirectoryAsset(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(UnityDirectoryAsset, path, *args, **kwargs)


class UnityFileRef:
    def __init__(self, db, asset, guid, fileid):
        self.db = db
        self.asset = asset
        self.id = int(fileid)
        self.guid = guid if self.id != 0 else None
        if self.guid is not None and type(self.guid) != int:
            self.guid = int(self.guid, base=16)

    @property
    def is_missing(self):
        if self.empty:
            return False
        asset = self.db.find_asset_by_guid(self.guid)
        if not asset:
            return True
        obj = asset.find_object_by_id(self.id)
        if not obj:
            return True
        return False

    @property
    def uuid(self):
        return (self.guid, self.id)

    @property
    def empty(self):
        return self.id == 0

    def __cmp__(self, other):
        return cmp(self.uuid, other.uuid)

    def __repr__(self):
        return self.print_relative_to(self.asset)

    def print_relative_to(self, parent_asset=None):
        if self.empty:
            return "null"

        if parent_asset and self.guid == parent_asset.guid:
            obj = parent_asset.find_object_by_id(self.id)
            if obj is None:
                return "missing internal reference to object {id:d} (&{guid:x}:{id:d})".format(
                    guid=self.guid, id=self.id)

            return "{type} &:{id:d}".format(
                type=obj.type.name, id=self.id)
        else:
            asset = self.db.find_asset_by_guid(self.guid)
            if asset is None:
                return "missing reference to asset {guid:x} (&{guid:x}:{id:d})".format(
                    guid=self.guid, id=self.id)

            path = os.path.relpath(asset.path, self.asset.path) \
                if self.asset is not None else asset.path

            obj = asset.find_object_by_id(self.id)
            if obj is None:
                return "missing reference to object {id:d} in {type} {path} (&{guid:x}:{id:d})".format(
                    type=asset.asset_type.__name__, path=path,
                    guid=self.guid, id=self.id)

            return "{type} {id:d} in {path} (&{guid:x}:{id:d})".format(
                type=obj.type.name, asset_type=asset.asset_type, path=path,
                guid=self.guid, id=self.id)

    @staticmethod
    def parse_from(db, data, asset=None, parent_guid=None):
        if parent_guid and type(parent_guid) != int:
            parent_guid = int(parent_guid, base=16)

        ref_id = data['fileID']
        ref_guid = data['guid'] if 'guid' in data else None
        if 'type' in data and int(data['type']) == 0:
            if ref_guid not in (
                    '0000000000000000e000000000000000',
                    '0000000000000000f000000000000000'):
                raise Exception(str(data))
            ref_guid = None
        elif 'type' in data and int(data['type']) not in (2, 3):
            raise Exception(str(data))
        return UnityFileRef(
            db=db, asset=asset, guid=(ref_guid or parent_guid), fileid=ref_id)


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
    elif type(value) == str:
        if '\n' not in value:
            return '{name}: {type} "{value}"'.format(
                name=name, type='str', value=value)
        else:
            return '{name}: {type} """\n    {value}\n    """'.format(
                name=name, type='str', value=value.strip().replace('\n', '\n    '))

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


class UnityPropertyReference:
    def __init__(self, obj, name, ref):
        self.object = obj
        self.name = name
        self.ref = ref

    @property
    def is_missing(self):
        return self.ref.is_missing

    def __repr__(self):
        return "{status} {object} &{guid:x}:{id:d} {name}: {ref}\n in {path}".format(
            status="Missing reference" if self.is_missing else "ref",
            object=self.object.type,
            guid=self.object.ref.guid,
            id=self.object.ref.id,
            name=self.name,
            ref=self.ref,
            path=os.path.relpath(
                self.object.asset.path, self.object.asset.db.root_dir)
        )


class UnitySceneGraphObject:
    def __init__(self, asset, ref, object_type, properties):
        self.asset = asset
        self.ref = ref
        self.type = object_type
        self.properties = properties
        self._flat_properties = None

    def get_references(self):
        return [
            UnityPropertyReference(self, name, ref)
            for name, ref in self.flat_properties.items()
            if type(ref) == UnityFileRef
        ]

    @property
    def flat_properties(self):
        if self._flat_properties is None:
            self._flat_properties = dict(list_flat_properties(self.properties))
        return self._flat_properties

    def __repr__(self):
        return "{type} {id} {path}\n{properties}".format(
            type=self.type,
            id=self.ref.id,
            path=self.asset.path if self.asset else '',
            properties='\n'.join([
                '  %s' % fmt_prop(name, value)
                for name, value in self.flat_properties.items()
            ])
        )


class UnityAssetSceneGraph(UnityAsset):
    def __init__(self, asset_type, path, *args, **kwargs):
        self.objects = None
        super().__init__(
            asset_type, path, loadable=True, *args, **kwargs)

    def find_object_by_id(self, object_id):
        if self.objects is None:
            self.load()
            self.db.update_asset(self)
        if str(object_id) in self.objects:
            return self.objects[str(object_id)]
        if int(object_id) in self.objects:
            return self.objects[int(object_id)]
        return None

    def get_all_refs(self):
        if not self.objects:
            self.load()
            self.db.update_asset(self)
        refs = []
        for obj in self.objects.values():
            refs += obj.get_references()
        return refs

    def get_missing_refs(self):
        return [
            ref for ref in self.get_all_refs()
            if ref.is_missing
        ]

    @property
    def is_loaded(self):
        return self.objects is not None

    def load(self):
        self.file.__class__ = UnitySceneDataFile
        self.file.load()
        db, guid = self.db, self.guid

        def parse_properties(data):
            if type(data) == str:
                if re.match(r'\-?[0-9]+\.?[0-9]*[eE]?-?[0-9]*$', data):
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
                    return UnityFileRef.parse_from(
                        db=db, asset=self, data=data, parent_guid=guid)
                else:
                    return {k: parse_properties(v) for k, v in data.items()}
            else:
                raise Exception(
                    "Unhandled type {}: {}".format(type(data), data))

        objects = [
            UnitySceneGraphObject(
                asset=self,
                ref=UnityFileRef(db=db, asset=self, guid=guid, fileid=ref_id),
                object_type=UnityType(name=obj['type'], typeid=obj['typeid']),
                properties=parse_properties(obj['data'])
            )
            for ref_id, obj in self.file.data.items()
        ]
        self.objects = {obj.ref.id: obj for obj in objects}

    def __repr__(self):
        if self.objects:
            objects = ''.join([
                '\n  %s' % str(obj).replace('\n', '\n  ')
                for obj in self.objects.values()
            ])
        else:
            objects = ''
        return super().__repr__() + objects


class UnityAssetPrefab(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super().__init__(
            UnityAssetPrefab, path, *args, **kwargs)


class UnityAssetScene(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super().__init__(
            UnityAssetScene, path, *args, **kwargs)


class UnityAssetMaterial(UnityAssetSceneGraph):
    def __init__(self, path, *args, **kwargs):
        super().__init__(
            UnityAssetMaterial, path, *args, **kwargs)


class UnityAssetCSharpScript(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(UnityAssetCSharpScript, path, *args, **kwargs)


class UnityAssetTexture(UnityAsset):
    def __init__(self, path, *args, **kwargs):
        super().__init__(UnityAssetTexture, path, *args, **kwargs)

    def find_object_by_id(self, id):
        if int(id) == 2800000:
            return self
        return None


IGNORED_UNITY_ASSET_TYPES = {
    '.txt', '.pdf', '.cginc', '.glsl', '.glslinc', '.asset', '.chm', '.md', '',
    '.json', '.inputactions', '.shader', '.wav', '.mp3', '.ogg',
    '.hlsl', '.shadergraph', '.shadersubgraph', '.blend', '.fbx',
    '.ttf', '.mtl', '.lighting', '.physicMaterial',
    '.controller', '.anim', '.cache', '.playable',
}

TEXTURE_2D_EXTS = {'.jpg', '.jpeg', '.png', '.psd', '.tga', '.tif'}
IGNORED_EXTS = {'.DS_Store', '.gitkeep', '.blend1', '.orig'}
UNITY_ASSET_EXT_TYPES = {
    '.prefab': UnityAssetPrefab,
    '.unity': UnityAssetScene,
    '.mat': UnityAssetMaterial,
    '.cs': UnityAssetCSharpScript,
}
UNITY_ASSET_EXT_TYPES.update({
    t: IgnoredAsset for t in IGNORED_UNITY_ASSET_TYPES
})
UNITY_ASSET_EXT_TYPES.update({
    t: UnityAssetTexture for t in TEXTURE_2D_EXTS
})


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

    def find_asset_by_guid(self, guid):
        if guid is None:
            return None

        if type(guid) != str:
            guid = "{:x}".format(guid)
        if guid in self.assets_by_guid:
            return self.assets_by_guid[guid]
        # print("Could not locate '%s' in assets!" % (
        #     guid,
        # ))

        return None

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

    def run_asset_update_parallel(self, job, assets_or_predicate):
        if type(assets_or_predicate) == list:
            assets = assets_or_predicate
        else:
            predicate = assets_or_predicate
            assets = [
                asset for asset in self.assets_by_path.values()
                if predicate(asset)
            ]
        print("Running {} on {} asset(s):\n{}".format(
            job, len(assets), '\n'.join([asset.path for asset in assets])))
        import time
        start_time = time.time()
        for asset in run_parallel(job, assets):
            self.update_asset(asset)
        stop_time = time.time()
        print("finished running {} on {} asset(s) in {:0.2f} second(s)".format(
            job, len(assets), stop_time - start_time))
        print()

    def load_missing_metafiles(self):
        self.run_asset_update_parallel(
            parallel_job_load_metafile,
            lambda asset: not asset.metafile.is_loaded)

    def load_all(self):
        self.run_asset_update_parallel(
            parallel_job_load_asset,
            lambda asset: asset.loadable and not asset.is_loaded)

    def get_all_refs(self):
        refs = []
        for asset in self.assets_by_path.values():
            if asset.loadable:
                refs += asset.get_all_refs()
        return refs

    def get_all_missing_refs(self):
        return [
            ref for ref in self.get_all_refs()
            if ref.is_missing
        ]

    def summarize_missing_refs(self):
        assets = list(self.assets_by_path.values())
        assets_missing_refs_count = 0
        missing_ref_total = 0
        for asset in assets:
            if not asset.loadable:
                continue
            missing_refs = asset.get_missing_refs()
            if len(missing_refs) > 0:
                assets_missing_refs_count += 1
                print("%s has %s missing ref(s):" % (
                    asset.path, len(missing_refs)))
                for ref in missing_refs:
                    missing_ref_total += 1
                    print("  {type} {id} {name}: {ref}".format(
                        type=ref.object.type,
                        id=ref.object.ref.id,
                        name=ref.name,
                        ref=ref.ref))
        print("%d / %d asset(s) are missing a total of %d references" % (
            assets_missing_refs_count, len(assets), missing_ref_total))


pool = None


def run_parallel(fcn, jobs):
    global pool
    if not pool:
        import multiprocessing as mp
        pool = mp.Pool(16)
    return pool.map(fcn, jobs)


def parallel_job_load_metafile(args):
    asset = args
    asset.load_metafile()
    return asset


def parallel_job_load_asset(asset):
    asset.load()
    return asset


def split_file_path_name_ext(path):
    base_path, file_name = os.path.split(path)
    file_name = file_name.rstrip('. \t')
    if file_name.endswith('.meta'):
        ext_parts = file_name[:-5].split('.')
        ext = '.'+ext_parts[-1] + '.meta' if len(ext_parts) > 1 else '.meta'
    else:
        ext_parts = file_name.split('.')
        ext = '.'+ext_parts[-1]
    name = file_name[:-len(ext)]
    return base_path, name, ext


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

        # ignore files we don't care about
        if ext in IGNORED_EXTS:
            return

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
        print("adding %s (ext '%s') as %s" % (path, ext, UNITY_ASSET_EXT_TYPES[ext]))
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
        self.db.load_all()


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
    #     if asset.loadable:
    #         print(asset)
    # print("%d asset(s)" % len(assets))
    db.summarize_missing_refs()



    # ASSET = "/Users/semery/projects/glitch-escape/Assets/GlitchEscape/Cutscenes/Cutscenes.prefab"
    # print(ASSET)
    # asset = db.assets_by_path[ASSET]
    # asset.load()
    # print(asset)
