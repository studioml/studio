# Using custom environment variables at runtime
You can add an env section to your yaml configuration file in order to send environment variables into your runner environment variables table.  Variables can be prefix with a $ sign if you wish to substitute local environment variables into your run configuration.  Be aware that all values are stored in clear text on the machine being used to submit and run the job.  Environment variableas are not stored within the StudioML database.  When transmitted to the runner the variables will be sent across a message queue that is authenticated however end-tyo-end ecryption is not assured.  If you wish to exchange secrets in a secured manner you will need to encrypt them into your configuration file and then decrypt your secrets within your python code used during the experiment.

# Customization of python environment for the workers
Sometimes your experiment relies on an older / custom version of some python package. For example, Keras API has changed quite a bit between versions 1 and 2. What if you are using new environment locally, but would like to re-run old experiments 
that needed older version of packages? Or, for example, you'd like to try if your code would work with the latest version of a package. 
TensorFlow Studio gives you such opportunity. 

    studio run --python-pkg=<package_name>==<package_version> <script.py>

allows you to run `<script.py>` on a remote / cloud worker with a specific version of a package. You can also omit `==<package_version>` part to install the latest version of the package (which may not be equal to the version in your environment)
Note that if package with a custom version has dependencies conflicting with current, the situation gets tricky. For now, it is up to the pip to resolve conflicts, in some cases it may fail; and you'll have to manually specify 
dependencies versions by adding more `--python-pkg` arguments.
