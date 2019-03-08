import yaml

AWSInstance = "aws" in list(
    yaml.load(
        open(
            "./test_config.yaml",
            "r"))["cloud"].keys())
GCPInstance = "gcloud" in list(
    yaml.load(
        open(
            "./test_config.yaml",
            "r"))["cloud"].keys())


def on_gcp():
    return GCPInstance


def on_aws():
    return AWSInstance
