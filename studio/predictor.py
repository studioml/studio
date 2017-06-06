import keras
#import tensorflow as tf
import argparse
import studio

def main():
    parser = argparse.ArgumentParser(
        description='TensorFlow Studio predictor. \
                     Usage: studio-predictor \
                     <arguments>')
    parser.add_argument('--config', help='configuration file', default=None)
    parser.add_argument('--experiment', help='Name of the experiment')

    args = parser.parse_args()

    config = studio.model.get_default_config()
    if args.config:
        with open(args.config) as f:
            config.update(yaml.load(f))


    fb = studio.model.get_db_provider(config)
    model = fb.get_experiment(args.experiment).get_model()
    
    print(model)


if __name__ == '__main__':
    main()
