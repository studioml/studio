import os

from studio.util.util import rand_string
"""
Utility functions for anything shared in common by ec2cloud_worker and
gcloud_worker
"""

INDENT = 4


def insert_user_startup_script(user_startup_script, startup_script_str,
                               logger):
    if user_startup_script is None:
        return startup_script_str

    try:
        with open(os.path.abspath(os.path.expanduser(
                user_startup_script))) as f:
            user_startup_script_lines = f.read().splitlines()
    except BaseException:
        if user_startup_script is not None:
            logger.warn("User startup script (%s) cannot be loaded" %
                        user_startup_script)
        return startup_script_str

    startup_script_lines = startup_script_str.splitlines()
    new_startup_script_lines = []
    whitespace = " " * INDENT
    for line in startup_script_lines:

        if line.startswith("studio remote worker") or \
                line.startswith("studio-remote-worker"):
            curr_working_dir = "curr_working_dir_%s" % rand_string(32)
            func_name = "user_script_%s" % rand_string(32)

            new_startup_script_lines.append("%s=$(pwd)\n" % curr_working_dir)
            new_startup_script_lines.append("cd ~\n")
            new_startup_script_lines.append("%s()(\n" % func_name)
            for user_line in user_startup_script_lines:
                if user_line.startswith("#!"):
                    continue
                new_startup_script_lines.append("%s%s\n" %
                                                (whitespace, user_line))

            new_startup_script_lines.append("%scd $%s\n" %
                                            (whitespace, curr_working_dir))
            new_startup_script_lines.append("%s%s\n" %
                                            (whitespace, line))
            new_startup_script_lines.append(")\n")
            new_startup_script_lines.append("%s\n" % func_name)
        else:
            new_startup_script_lines.append("%s\n" % line)

    new_startup_script = "".join(new_startup_script_lines)
    logger.info('Inserting the following user startup script'
                ' into the default startup script:')
    logger.info("\n".join(user_startup_script_lines))

    # with open("/home/jason/Desktop/script.sh", 'wb') as f:
    #     f.write(new_startup_script)
    # sys.exit()

    return new_startup_script
