import argparse
import sys
import time
from terminaltables import AsciiTable

from . import model
from . import logs

_my_logger = None


def print_help():
    print('Usage: studio runs [command] arguments')
    print('\ncommand can be one of the following:')
    print('')
    print('\tlist [username] - display experiments')
    print('\tstop [experiment] - stop running experiment')
    print('\tkill [experiment] - stop and delete experiment')
    print('')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument(
        '--short', '-s', help='Brief output - names of experiments only',
        action='store_true')

    cli_args, script_args = parser.parse_known_args(sys.argv)

    get_logger().setLevel(10)

    if len(script_args) < 2:
        get_logger().critical('No command provided!')
        parser.print_help()
        print_help()
        return

    cmd = script_args[1]

    if cmd == 'list':
        _list(script_args[2:], cli_args)
    elif cmd == 'stop':
        _stop(script_args[2:], cli_args)
    elif cmd == 'kill':
        _kill(script_args[2:], cli_args)

    else:
        get_logger().critical('Unknown command ' + cmd)
        parser.print_help()
        print_help()
        return


def _list(args, cli_args):
    with model.get_db_provider(cli_args.config) as db:
        if len(args) == 0:
            experiments = db.get_user_experiments()
        elif args[0] == 'project':
            assert len(args) == 2
            experiments = db.get_project_experiments(args[1])
        elif args[0] == 'users':
            assert len(args) == 1
            users = db.get_users()
            for u in users:
                print(users[u].get('email'))
            return
        elif args[0] == 'user':
            assert len(args) == 2
            users = db.get_users()
            user_ids = [u for u in users if users[u].get('email') == args[1]]
            assert len(user_ids) == 1, \
                'The user with email ' + args[1] + \
                'not found!'
            experiments = db.get_user_experiments(user_ids[0])
        elif args[0] == 'all':
            assert len(args) == 1
            users = db.get_users()
            experiments = []
            for u in users:
                experiments += db.get_user_experiments(u)
        else:
            get_logger().critical('Unknown command ' + args[0])
            return

        if cli_args.short:
            for e in experiments:
                print(e)
            return

        experiments = [db.get_experiment(e) for e in experiments]

    experiments.sort(key=lambda e: -e.time_added)
    table = [['Time added', 'Key', 'Project', 'Status']]

    for e in experiments:
        table.append([
            time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.time_added)),
            e.key,
            e.project,
            e.status])

    print(AsciiTable(table).table)


def _stop(args, cli_args):
    with model.get_db_provider(cli_args.config) as db:
        for e in args:
            get_logger().info('Stopping experiment ' + e)
            db.stop_experiment(e)


def _kill(args, cli_args):
    with model.get_db_provider(cli_args.config) as db:
        for e in args:
            get_logger().info('Deleting experiment ' + e)
            db.delete_experiment(e)


def get_logger():
    global _my_logger
    if not _my_logger:
        _my_logger = logs.getLogger('studio-runs')
    return _my_logger


if __name__ == '__main__':
    main()
