import os
import yaml


class Cache:
    def __init__(self, cache_path):
        self.cache_path = cache_path
        if not os.path.exists(cache_path):
            dirs, file = os.path.split(cache_path)
            if dirs and not os.path.exists(dirs):
                os.makedirs(dirs)
            self.entries = {}
        else:
            with open(self.cache_path, 'r') as f:
                entries = yaml.load(f, yaml.CBaseLoader)
            self.entries = entries or {}

    def clear(self):
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        self.entries = {}

    def save_cache(self):
        print("saving data to {}:".format(self.cache_path))
        for k, v in self.entries.items():
            print("  '{}': {}".format(k, v))
        print("yaml:\n{}\n".format(yaml.dump(self.entries)))
        if not os.path.exists(self.cache_path):
            dirs, file = os.path.split(self.cache_path)
            if dirs and not os.path.exists(dirs):
                os.makedirs(dirs)
            self.entries = {}
        with open(self.cache_path, 'w') as f:
            yaml.dump(self.entries, f)

    def cached(self, key, fcn, *args, **kwargs):
        if key in self.entries:
            return self.entries[key]
        value = fcn(*args, **kwargs)
        self.entries[key] = value
        self.save_cache()
        return value

    def __getitem__(self, key):
        if key in self.entries:
            return self.entries[key]
        return None

    def __setitem__(self, key, value):
        self.entries[key] = value

    caches = {}


def cache(name):
    if name not in Cache.caches:
        path = os.path.join('.cache', '.' + name + '.cache')
        Cache.caches[name] = Cache(path)
    return Cache.caches[name]
