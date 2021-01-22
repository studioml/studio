import os
import shutil
import time
import tarfile
import tempfile

from . import fs_tracker
from . import util
from .util import get_temp_filename, rm_rf

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
    if os.path.isdir(local_path):
        _tar_artifact_directory(local_path, tar_filename,
                                key, ignore_filepath, logger)
    else:
        _tar_artifact_single_file(local_path, tar_filename,
                                  key, logger)
    toc = time.time()

    logger.debug('tar finished in %f s', (toc - tic))
    return tar_filename

def _tar_artifact_directory(local_path: str,
                            tar_filename: str,
                            key,
                            ignore_filepath, logger):
    tf = None
    try:
        debug_str: str = ("Tarring artifact directory. " +
                     "tar_filename = {0}, " +
                     "local_path = {1}, " +
                     "key = {2}").format(tar_filename, local_path, key)
        if ignore_filepath is not None:
            debug_str += ", exclude = {0}".format(ignore_filepath)
        logger.debug(debug_str)

        tf = tarfile.open(tar_filename, 'w')
        files_list = os.listdir(local_path)
        for file_name in files_list:
            tf.add(os.path.join(local_path, file_name), arcname=file_name)
    except Exception as exc:
        msg: str =\
            "FAILED to create tarfile: {0} for artifact {1} reason: {2}"\
            .format(tar_filename, local_path, exc)
        util.report_fatal(msg, logger)
    finally:
        if tf is not None:
            tf.close()

def _tar_artifact_single_file(local_path: str,
                            tar_filename: str,
                            key,
                            logger):
    tf = None
    try:
        debug_str: str = ("Tarring artifact single file. " +
                     "tar_filename = {0}, " +
                     "local_path = {1}, " +
                     "key = {2}").format(tar_filename, local_path, key)
        logger.debug(debug_str)

        tf = tarfile.open(tar_filename, 'w')
        _, last_name = os.path.split(local_path)
        tf.add(local_path, "./" + last_name)
    except Exception as exc:
        msg: str =\
            "FAILED to create tarfile: {0} for artifact {1} reason: {2}"\
            .format(tar_filename, local_path, exc)
        util.report_fatal(msg, logger)
    finally:
        if tf is not None:
            tf.close()

def _get_single_file_name(items_list):
    if len(items_list) == 1 and items_list[0].startswith("./"):
        return items_list[0][2:]
    return None

def untar_artifact(local_path: str, tar_filename: str, logger):

    if local_path != '/' and local_path.endswith('/'):
        local_path = local_path[0..len(local_path)-1]

    logger.debug("Untarring %s", tar_filename)

    tf = None
    try:
        tf = tarfile.open(tar_filename, 'r')
        tar_items = tf.getnames()
        logger.debug('List of files in the tar: ' + str(tar_items))

        single_file_name = _get_single_file_name(tar_items)
        if single_file_name is None:
            rm_rf(local_path)
            # Extract tar file into directory "local_path"
            os.makedirs(local_path, exist_ok=True)
            logger.debug("Untarring %s to dir. %s", tar_filename, local_path)
            tf.extractall(local_path)
        else:
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.debug("Untarring %s to temp. dir. %s", tar_filename, temp_dir)
                tf.extractall(temp_dir)
                rm_rf(local_path)
                temp_path: str = os.path.join(temp_dir, single_file_name)
                logger.debug("Copying single file %s to %s", temp_path, local_path)
                shutil.copy2(temp_path, local_path)

    except Exception as exc:
        msg: str = \
            "FAILED to extract tarfile: {0} for artifact {1} reason: {2}" \
                .format(tar_filename, local_path, exc)
        logger.error(msg)
    finally:
        if tf is not None:
            tf.close()
