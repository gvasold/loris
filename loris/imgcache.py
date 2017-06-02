import os.path as path
from os import makedirs, symlink, unlink, error as os_error
from urllib import unquote
from logging import getLogger
from datetime import datetime
from errno import EEXIST




logger = getLogger(__name__)
class ImageCache(dict):
    '''
    This is the default image cache.
    '''
    def __init__(self, config):
        self.cache_root = config['cache_dp']

    def __contains__(self, image_request):
        return path.exists(self.get_request_cache_path(image_request))

    def __getitem__(self, image_request):
        fp = self.get(image_request)
        if fp is None:
            raise KeyError
        return fp

    @staticmethod
    def _link(source, link_name):
        if source == link_name:
            logger.warn('Circular symlink requested from %s to %s; not creating symlink' % (link_name, source))
            return
        link_dp = path.dirname(link_name)
        if not path.exists(link_dp):
            makedirs(link_dp)
        if path.lexists(link_name): # shouldn't be the case, but helps debugging
            unlink(link_name)
        symlink(source, link_name)
        logger.debug('Made symlink from %s to %s' % (link_name, source))

    def __setitem__(self, image_request, canonical_fp):
        # Because we're working with files, it's more practical to put derived
        # images where the cache expects them when they are created (i.e. by
        # Loris#_make_image()), so __setitem__, as defined by the dict API
        # doesn't really work. Instead, the logic related to where an image
        # should be put is encapulated in the ImageCache#get_request_cache_path
        # and ImageCache#get_canonical_cache_path methods.
        #
        # Instead, __setitem__ simply makes a symlink in the cache from the
        # requested syntax to the canonical syntax to enable faster lookups of
        # the same non-canonical request the next time.
        #
        # So: when Loris#_make_image is called, it gets a path from
        # ImageCache#get_canonical_cache_path and passes that to the
        # transformer.
        if not image_request.is_canonical:
            requested_fp = self.get_request_cache_path(image_request)
            ImageCache._link(canonical_fp, requested_fp)

    def __delitem__(self, image_request):
        # if we ever decide to start cleaning our own cache...
        pass

    def get(self, image_request):
        '''Returns (str, ):
            The path to the file or None if the file does not exist.
        '''
        cache_fp = self.get_request_cache_path(image_request)
        last_mod = datetime.utcfromtimestamp(path.getmtime(cache_fp))
        if path.exists(cache_fp):
            return (cache_fp, last_mod)
        else:
            return None

    def get_request_cache_path(self, image_request):
        request_fp = image_request.as_path
        return path.realpath(path.join(self.cache_root, unquote(request_fp)))

    def get_canonical_cache_path(self, image_request):
        canonical_fp = image_request.canonical_as_path
        return path.realpath(path.join(self.cache_root, unquote(canonical_fp)))

    def create_dir_and_return_file_path(self, image_request):
        target_fp = self.get_canonical_cache_path(image_request)
        target_dp = path.dirname(target_fp)
        try:
            makedirs(target_dp)
        except os_error as ose:
            if ose.errno == EEXIST:
                pass
            else:
                raise
        return target_fp
