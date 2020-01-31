Setting up experiment storage and database in local filesystem
==============================================================

This page describes how to setup studioml to use
local filesystem for storing experiment artifacts and meta-data.
With this option, there is no need to setup any external
connection to S3/Minio/GCS etc.

StudioML configuration
--------------------

::

      "studio_ml_config": {

          ...

          "database": {
                    "type": "local",
                    "endpoint": SOME_DB_LOCAL_PATH,
                    "bucket": DB_BUCKET_NAME,
                    "authentication": "none"
          },
          "storage": {
                    "type": "local",
                    "endpoint": SOME_ARTIFACTS_LOCAL_PATH,
                    "bucket": ARTIFACTS_BUCKET_NAME,
          }

          ...
      }


With StudioML database type set to "local",
all experiment meta-data will be stored locally under
directory: SOME_DB_LOCAL_PATH/DB_BUCKET_NAME.
Similarly, with storage type set to "local",
all experiment artifacts will be stored locally under
directory: SOME_ARTIFACTS_LOCAL_PATH/ARTIFACTS_BUCKET_NAME.

Note: if you are using "local" mode, it is recommended to use it
for both storage and database configuration.
But it's technically possible to mix, for example, local storage configuration
and S3-based database configuration etc.

