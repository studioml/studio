

def parse_hardware(runner_args, config={}):
    resources_needed = {}
    parse_list = ['gpus', 'cpus', 'ram', 'hdd', 'num-workers', 'num-ps']
    for key in parse_list:
        from_args = runner_args.__dict__.get(key)
        from_config = config.get(key)
        if from_args is not None:
            resources_needed[key] = from_args
        elif from_config is not None:
            resources_needed[key] = from_config

    return resources_needed


def get_num_machines(resources_needed, num_experiments):
    num_experiments = int(num_experiments) if num_experiments else 1
    return (int(resources_needed.get('num-workers', 1)) + int(resources_needed.get('num-ps', 0))) * num_experiments
