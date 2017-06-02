"""
Start a Loris instance for development.
This script uses a custom configuration (~/etc/gamsloris.conf)
and suppresses the forced use of SimpleFSResolver as defined
for debug mode in loris/webapp.py.

Running test.py is not affected by this!
"""
import os.path as path
import sys
from werkzeug.serving import run_simple
from loris.webapp import create_app, read_config, Loris
from loris import transforms

def create_app(debug=False, debug_jp2_transformer='kdu', config_file_path=''):
    if debug:
        config = get_debug_config(config_file_path, debug_jp2_transformer)
    else:
        config = read_config(config_file_path)
    return Loris(config)

# we have to override this because we want to test alternative resolvers
def get_debug_config(config_file_path, debug_jp2_transformer):
    # change a few things, read the config and set up logging
    project_dp = path.dirname(path.dirname(path.realpath(__file__)))
    if not config_file_path:
        config_file_path = path.join(project_dp, 'etc', 'loris2.conf')

    config = read_config(config_file_path)

    config['logging']['log_to'] = 'console'
    config['logging']['log_level'] = 'DEBUG'

    # override some stuff to look at relative or tmp directories.
    config['loris.Loris']['www_dp'] = path.join(project_dp, 'www')
    config['loris.Loris']['tmp_dp'] = '/tmp/loris/tmp'
    config['loris.Loris']['enable_caching'] = True
    config['img.ImageCache']['cache_dp'] = '/tmp/loris/cache/img'
    config['img_info.InfoCache']['cache_dp'] = '/tmp/loris/cache/info'
#    config['resolver']['impl'] = 'loris.resolver.SimpleFSResolver'
    config['resolver']['src_img_root'] = path.join(project_dp,'tests','img')
    if debug_jp2_transformer == 'opj':
        from loris.transforms import OPJ_JP2Transformer
        opj_decompress = OPJ_JP2Transformer.local_opj_decompress_path()
        config['transforms']['jp2']['opj_decompress'] = path.join(project_dp, opj_decompress)
        libopenjp2_dir = OPJ_JP2Transformer.local_libopenjp2_dir()
        config['transforms']['jp2']['opj_libs'] = path.join(project_dp, libopenjp2_dir)
    else: # kdu
        from loris.transforms import KakaduJP2Transformer
        kdu_expand = KakaduJP2Transformer.local_kdu_expand_path()
        config['transforms']['jp2']['kdu_expand'] = path.join(project_dp, kdu_expand)
        libkdu_dir = KakaduJP2Transformer.local_libkdu_dir()
        config['transforms']['jp2']['kdu_libs'] = path.join(project_dp, libkdu_dir)

    return config


if __name__ == '__main__':
    project_dp = path.dirname(path.realpath(__file__))
    sys.path.append(path.join(project_dp)) # to find any local resolvers
    app = create_app(debug=True, config_file_path = path.join(project_dp, 'etc', 'gamsloris.conf')) # or 'opj'
    run_simple('localhost', 5004, app, use_debugger=True, use_reloader=True)


