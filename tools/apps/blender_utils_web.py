import os
import re
from bs4 import BeautifulSoup
import urllib3
import certifi
http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                           ca_certs=certifi.where())


def get_blender_download_page_links(url):
    req = http.request('GET', url)
    if req.status != 200:
        raise Exception(
            "'{}' does not exist (error {})".format(url, req.status))
    soup = BeautifulSoup(req.data, "html5lib")
    for tag in soup.findAll('a'):
        link = tag['href']
        if 'blender' in link.lower():
            yield os.path.join(url, link.rstrip('/'))


def get_blender_web_archive_version_links():
    versions = {}
    regex = re.compile(r'[Bb]lender(\d+)\.(\d+)([a-z]*)')
    for url in get_blender_download_page_links(RELEASE_URL):
        match = re.match(regex, os.path.split(url)[1])
        if not match:
            continue
        major, minor, etc = match.group(1, 2, 3)
        # mainline release
        if etc is None or etc == '':
            versions['{}.{}'.format(major, minor)] = url
            continue
        # Normalize 'alpha', 'beta', 'abeta' to 'a', 'b', 'a' versions
        # (respectively)
        if etc in ('a', 'b', 'c'):
            versions['{}.{}{}'.format(major, minor, etc)] = url
        elif etc == 'alpha':
            versions['{}.{}a'.format(major, minor)] = url
        elif etc == 'beta':
            versions['{}.{}b'.format(major, minor)] = url
        elif etc == 'abeta':
            versions['{}.{}a'.format(major, minor)] = url
        else:
            print("unhandled version identifier: '{}.{}', '{}'".format(
                major, minor, etc))
    return versions


RELEASE_URL = 'http://download.blender.org/release/'


def get_blender_version_download_links(version, platform=None):
    versions = get_blender_web_archive_version_links()
    url = versions[version]
    download_links = list(get_blender_download_page_links(url))
    if platform is None:
        return set(download_links)

    matching_links = set()
    platform = platform.lower()
    for url in download_links:
        name = os.path.split(url)[1]
        if platform in name.lower():
            # print("'{}' matched '{}'".format(platform, name))
            matching_links.add(url)
            # else:
            #     print("'{}' did not match '{}'".format(platform, name))
    return matching_links or set(download_links)


if __name__ == '__main__':
    # for link in get_blender_links(RELEASE_URL):
    #     print(link)

    # version_urls = get_blender_web_archive_version_links()
    # for version, url in version_urls.items():
    #     print("{}: {}".format(version, url))
    downloads = get_blender_version_download_links('1.80', 'mac')
    for download in downloads:
        print(download)
    # print(get_blender_release_downloads('2.80', 'macos'))

    # print(list(get_blender_release_downloads('2.80')))

    # req = http.request('GET', RELEASE_URL)
    # print(req.status, req.data)
