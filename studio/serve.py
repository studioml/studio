import sys
import argparse
from studio import runner


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        '--wrapper', '-w',
        help='python script with function create_model ' +
             'that takes modeldir '
        '(that is, directory where experiment saves ' +
        'the checkpoints etc)' +
        'and returns dict -> dict function (model).' +
        'By default, studio-serve will try to determine ' +
        'this function automatically.',
        default=None
    )

    argparser.add_argument('--port',
                           help='port to run Flask server on',
                           type=int,
                           default=5000)

    argparser.add_argument('--host',
                           help='host name.',
                           default='0.0.0.0')

    argparser.add_argument(
        '--killafter',
        help='Shut down after this many seconds of inactivity',
        default=3600)

    options, other_args = argparser.parse_known_args(sys.argv[1:])
    serve_args = ['studio::serve_main']

    assert len(other_args) >= 1
    experiment_key = other_args[-1]
    runner_args = other_args[:-1]
    runner_args.append('--reuse={}/modeldir:modeldata'.format(experiment_key))
    runner_args.append('--force-git')
    runner_args.append('--port=' + str(options.port))

    if options.wrapper:
        serve_args.append('--wrapper=' + options.wrapper)
        serve_args.append('--port=' + str(options.port))

    serve_args.append('--host=' + options.host)
    serve_args.append('--killafter=' + str(options.killafter))

    total_args = runner_args + serve_args
    runner.main(total_args)


if __name__ == '__main__':
    main()
