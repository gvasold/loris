import os.path
from collections import OrderedDict
from threading import Lock
from urllib import unquote
from logging import getLogger
from datetime import datetime
import errno
from loris.img_info import ImageInfo


logger = getLogger(__name__)

class InfoCache(object):
    """A dict-like cache for ImageInfo objects. The n most recently used are
    also kept in memory; all entries are on the file system.

    One twist: you put in an ImageInfo object, but get back a two-tuple, the
    first member is the ImageInfo, the second member is the UTC date and time
    for when the info was last modified.

    Note that not all dictionary methods are implemented; just basic getters,
    put (`instance[indent] = info`), membership, and length. There are no
    iterators, views, default, update, comparators, etc.

    Slots:
        http_root (str): See below
        https_root (str): See below
        size (int): See below.
        _dict (OrderedDict): The map.
        _lock (Lock): The lock.
    """
    __slots__ = ( 'http_root', 'https_root', 'size', '_dict', '_lock')

    def __init__(self, config, size=500):
        """
        Args:
            config (dict):
                The img_info.InfoCache configuration dict.
            size (int):
                Max entries before the we start popping (LRU).
        """
        root = config['cache_dp']
        self.http_root = os.path.join(root, 'http')
        self.https_root = os.path.join(root, 'https')
        self.size = size
        self._dict = OrderedDict(last=False) # keyed with the URL, so we don't
                                             # need toseparate HTTP and HTTPS
        self._lock = Lock()

    def _which_root(self, request):
        if request.url.startswith('https'):
            return self.https_root
        else:
            return self.http_root

    @staticmethod
    def ident_from_request(request):
        return '/'.join(request.path[1:].split('/')[:-1])

    def _get_info_fp(self, request):
        ident = InfoCache.ident_from_request(request)
        cache_root = self._which_root(request)
        path = os.path.join(cache_root, unquote(ident), 'info.json')
        return path

    def _get_color_profile_fp(self, request):
        ident = InfoCache.ident_from_request(request)
        cache_root = self._which_root(request)
        path = os.path.join(cache_root, unquote(ident), 'profile.icc')
        return path

    def get(self, request):
        '''
        Returns:
            ImageInfo if it is in the cache, else None
        '''
        info_and_lastmod = None
        with self._lock:
            info_and_lastmod = self._dict.get(request.url)
        if info_and_lastmod is None:
            info_fp = self._get_info_fp(request)
            if os.path.exists(info_fp):
                # from fs
                info = ImageInfo.from_json(info_fp)

                icc_fp = self._get_color_profile_fp(request)
                if os.path.exists(icc_fp):
                    with open(icc_fp, "rb") as f:
                        info.color_profile_bytes = f.read()
                else:
                    info.color_profile_bytes = None

                lastmod = datetime.utcfromtimestamp(os.path.getmtime(info_fp))
                info_and_lastmod = (info, lastmod)
                logger.debug('Info for %s read from file system' % (request,))
                # into mem:
                self._dict[request.url] = info_and_lastmod

        return info_and_lastmod

    def has_key(self, request):
        return os.path.exists(self._get_info_fp(request))

    # def __len__(self):
    #     w = os.walk
    #     ff = fnmatch.filter
    #     pat = STAR_DOT_JSON
    #     return len([_ for fp in ff(fps, pat) for r,dps,fps in w(self.root)])

    def __contains__(self, request):
        return self.has_key(request)

    def __getitem__(self, request):
        info_lastmod = self.get(request)
        if info_lastmod is None:
            raise KeyError
        else:
            return info_lastmod

    def __setitem__(self, request, info):
        # to fs
        logger.debug('request passed to __setitem__: %s' % (request,))
        info_fp = self._get_info_fp(request)
        dp = os.path.dirname(info_fp)
        if not os.path.isdir(dp):
            try:
                os.makedirs(dp)
                logger.debug('Created %s' % (dp,))
            except OSError as e: # this happens once and a while; not sure why
                if e.errno == errno.EEXIST:
                    pass
                else:
                    raise

        with open(info_fp, 'w') as f:
            f.write(info.to_json())
            f.close()
            logger.debug('Created %s' % (info_fp,))

        if info.color_profile_bytes:
            icc_fp = self._get_color_profile_fp(request)
            with open(icc_fp, 'wb') as f:
                f.write(info.color_profile_bytes)
                f.close()
                logger.debug('Created %s' % (icc_fp,))

        # into mem
        lastmod = datetime.utcfromtimestamp(os.path.getmtime(info_fp))
        with self._lock:
            while len(self._dict) >= self.size:
                self._dict.popitem(last=False)
            self._dict[request.url] = (info,lastmod)

    def __delitem__(self, request):
        with self._lock:
            del self._dict[request]

        info_fp = self._get_info_fp(request)
        os.unlink(info_fp)

        icc_fp = self._getcolor_profile_bytes(request)
        if os.path.exists(icc_fp):
            os.unlink(icc_fp)

        os.removedirs(os.path.dirname(info_fp))
