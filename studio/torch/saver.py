"""Tools to save/restore model from checkpoints."""

import os
try:
    import torch
except ImportError:
    torch = None


def load_checkpoint(model, optimizer, model_dir, map_to_cpu=False):
    path = os.path.join(model_dir, 'checkpoint')
    if os.path.exists(path):
        print("Loading model from %s" % path)
        if map_to_cpu:
            checkpoint = torch.load(
                path, map_location=lambda storage, location: storage)
        else:
            checkpoint = torch.load(path)
        old_state_dict = model.state_dict()
        for key in old_state_dict.keys():
            if key not in checkpoint['model']:
                checkpoint['model'][key] = old_state_dict[key]
        model.load_state_dict(checkpoint['model'])
        optimizer.load_state_dict(checkpoint['optimizer'])
        return checkpoint.get('step', 0)
    return 0


def save_checkpoint(model, optimizer, step, model_dir, ignore=[]):
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    path = os.path.join(model_dir, 'checkpoint')
    state_dict = model.state_dict()
    if ignore:
        for key in state_dict.keys():
            for item in ignore:
                if key.startswith(item):
                    state_dict.pop(key)
    torch.save({
        'model': state_dict,
        'optimizer': optimizer.state_dict(),
        'step': step
    }, path)


class Saver(object):
    """Class to manage save and restore for the model and optimizer."""

    def __init__(self, model, optimizer):
        self._model = model
        self._optimizer = optimizer

    def restore(self, model_dir, map_to_cpu=False):
        """Restores model and optimizer from given directory.

        Returns:
           Last training step for the model restored.
        """
        last_step = load_checkpoint(
            self._model, self._optimizer, model_dir, map_to_cpu)
        return last_step

    def save(self, model_dir, step):
        """Saves model and optimizer to given directory.

        Args:
           model_dir: Model directory to save.
           step: Current training step.
        """
        save_checkpoint(self._model, self._optimizer, step, model_dir)
