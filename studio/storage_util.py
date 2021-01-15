import os
import time
import subprocess
import tarfile

from . import fs_tracker
from . import util
from .util import compression_to_taropt, sixdecode, get_temp_filename

def _find_ignore_list(local_path: str):
    if os.path.isdir(local_path):
        base_dir = local_path
    else:
        base_dir, last_name = os.path.split(local_path)
    ignore_filepath = os.path.join(base_dir, ".studioml_ignore")
    if os.path.exists(ignore_filepath) and \
       not os.path.isdir(ignore_filepath):
        return ignore_filepath
    else:
        return None

def tar_artifact(local_path: str, key: str,
                 compression: str, logger, cache: bool = True):
    tar_filename: str = get_temp_filename() + ".tar"

    if local_path != '/' and local_path.endswith('/'):
        local_path = local_path[0..len(local_path)-1]

    head_path, last_name = os.path.split(local_path)

    #TODO: ASD process ignore files list if present:
    ignore_filepath = _find_ignore_list(local_path)
    if ignore_filepath is not None:
        logger.info("NOT PROCESSED: ignore files list %s for artifact %s.",
                    ignore_filepath, local_path)

    if cache and key:
        cache_path = fs_tracker.get_artifact_cache(key)
        if cache_path != local_path:
            msg: str =\
                "NOT IMPLEMENTED: artifact local path and cache location differ: {0} vs {1}."\
                    .format(local_path, cache_path)
            logger.error(msg)
            raise NotImplementedError(msg)

    tic = time.time()
    tf = None
    try:
        debug_str: str = ("Tarring artifact. " +
                     "tar_filename = {0}, " +
                     "local_path = {1}, " +
                     "key = {2}").format(tar_filename, local_path, key)
        if ignore_filepath is not None:
            debug_str += ", exclude = {0}".format(ignore_filepath)
        logger.debug(debug_str)

        tf = tarfile.open(tar_filename, 'w')
        tf.add(local_path, arcname=last_name)
    except Exception as exc:
        msg: str =\
            "FAILED to create tarfile: {0} for artifact {1} reason: {2}"\
            .format(tar_filename, local_path, exc)
        util.report_fatal(msg)
    finally:
        if tf is not None:
            tf.close()
    toc = time.time()

    logger.debug('tar finished in %d s', (toc - tic))
    return tar_filename

    # if os.path.isdir(local_path):
    #     local_basepath = local_path
    #     local_nameonly = '.'
    #
    # else:
    #     local_nameonly = os.path.basename(local_path)
    #     local_basepath = os.path.dirname(local_path)
    #
    # ignore_arg = ''
    # ignore_filepath = os.path.join(local_basepath, ".studioml_ignore")
    # if os.path.exists(ignore_filepath) and \
    #         not os.path.isdir(ignore_filepath):
    #     ignore_arg = "--exclude-from={0}".format(ignore_filepath)
    #     logger.debug('.studioml_ignore found: {0},'
    #                       ' files listed inside will'
    #                       ' not be tarred or uploaded'
    #                       .format(ignore_filepath))
    #
    # if cache and key:
    #     cache_dir = fs_tracker.get_artifact_cache(key)
    #     if cache_dir != local_path:
    #         debug_str = "Copying local path {0} to cache {1}" \
    #             .format(local_path, cache_dir)
    #         if ignore_arg != '':
    #             debug_str += ", excluding files in {0}" \
    #                 .format(ignore_filepath)
    #         logger.debug(debug_str)
    #
    #         util.rsync_cp(local_path, cache_dir, ignore_arg, logger)
    #
    # debug_str = ("Tarring artifact. " +
    #              "tar_filename = {0}, " +
    #              "local_path = {1}, " +
    #              "key = {2}").format(tar_filename, local_path, key)
    #
    # if ignore_arg != '':
    #     debug_str += ", exclude = {0}".format(ignore_filepath)
    # logger.debug(debug_str)
    #
    # tarcmd = 'tar {0} {1} -cf {2} -C {3} {4}'.format(
    #     ignore_arg,
    #     compression_to_taropt(compression),
    #     tar_filename,
    #     local_basepath,
    #     local_nameonly)
    # logger.debug("Tar cmd = {0}".format(tarcmd))
    #
    # tic = time.time()
    # tarp = subprocess.Popen(['/bin/bash', '-c', tarcmd],
    #                         stdout=subprocess.PIPE,
    #                         stderr=subprocess.STDOUT,
    #                         close_fds=True)
    #
    # tarout, tarerr = tarp.communicate()
    # toc = time.time()
    #
    # if tarp.returncode != 0:
    #     msg: str = 'tar {0} had a non-zero return code! {1}' \
    #         .format(tar_filename, tarp.returncode)
    #     msg += 'tar cmd = {0}'.format(tarcmd)
    #     msg = msg + 'tar stdout output: \n ' + sixdecode(tarout)
    #     msg = msg + 'tar stderr output: \n ' + str(tarerr)
    #     util.report_fatal(msg)
    #
    # logger.debug('tar finished in %d s', (toc - tic))
    # return tar_filename

def untar_artifact(local_path: str, tar_filename: str, logger):
    local_basepath: str = os.path.dirname(local_path)

    # first, figure out if the tar file has a base path of .
    # or not
    logger.debug("Untarring {0}".format(tar_filename))
    listtar, _ = subprocess.Popen(['tar', '-tf', tar_filename],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  close_fds=True
                                  ).communicate()
    listtar = listtar.strip().split(b'\n')
    listtar = [s.decode('utf-8') for s in listtar]

    isTarFromDotDir = False
    logger.debug('List of files in the tar: ' + str(listtar))
    if listtar[0].startswith('./'):
        # Files are archived into tar from .; adjust path
        # accordingly
        isTarFromDotDir = True
        basepath = local_path
    else:
        basepath = local_basepath

    tarcmd = ('mkdir -p {} && ' +
              'tar -xf {} -C {} --keep-newer-files') \
        .format(basepath, tar_filename, basepath)

    logger.debug('Tar cmd = {0}'.format(tarcmd))

    tarp = subprocess.Popen(
        ['/bin/bash', '-c', tarcmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True)

    tarout, tarerr = tarp.communicate()
    if tarp.returncode != 0:
        msg: str = 'tar {0} had a non-zero return code! {1}' \
            .format(tar_filename, tarp.returncode)
        msg += 'tar cmd = {0}'.format(tarcmd)
        msg = msg + 'tar stdout output: \n ' + str(tarout)
        msg = msg + 'tar stderr output: \n ' + str(tarerr)
        util.report_fatal(msg)

    if len(listtar) == 1 and not isTarFromDotDir:
        # Here we protect ourselves from the corner case,
        # when we try to move A/. folder to A.
        # os.rename() will fail to do that.
        actual_path = os.path.join(basepath, listtar[0])
        logger.debug('Renaming {0} into {1}'.format(
                     actual_path, local_path))
        util.retry(lambda: os.rename(actual_path, local_path),
              no_retries=5,
              sleep_time=1,
              exception_class=OSError,
              logger=logger)
