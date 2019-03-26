import yaml

AWSInstance = "aws" in list(
    yaml.load(
        open(
            "tests/test_config.yaml",
            "r"))["cloud"].keys())
GcloudInstance = "gcloud" in list(
    yaml.load(
        open(
            "tests/test_config.yaml",
            "r"))["cloud"].keys())


def on_gcp():
    return GcloudInstance


def on_aws():
    return AWSInstance
