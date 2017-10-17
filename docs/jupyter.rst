Jupyter / ipython notebooks
===========================

Studio can be used not only with scripts, but also with
jupyter notebooks. The main idea is as follows - 
the cell annotated with a special cell magic is being treated 
as a separate script; and the variables are being passed in and 
out as artifacts (this means that all variables the cell 
depends on have to be pickleable). The script can then be run 
either locally (in which case the main benefit of studio 
is keeping track of all runs of the cell), or in the cloud / remotely. 

To use Studio in your notebook, add 

::

    from studio import magics 

to the import section of your notebook.

Then annotate the cell that you'd like to run via studio with

::

    %%studio_run <optional_arguments>

This will execute the statements in the cell using studio,
also passing ``<optional_arguments>`` to the runner. 
For example, let's imagine that a variable ``x`` is declared in 
your notebook. Then 

::

    %%studio_run --cloud=gcloud
    x += 1

will do the increment of the variable ``x`` in the notebook namespace
using a google cloud compute 
instance (given that increment of a variable in python does not take a millisecond,
spinning up an entire instance to do that is probably the most wasteful thing you 
have seen today, but you get the idea :). The ``%%studio_run`` cell magic 
accepts the same arguments as the ``studio run`` command, please refer to 
`<cloud.rst>` for a more involved discussion of cloud and hardware selection options.

Every run with studio will get a unique key and can be viewed as an experiment in
studio ui. 

The only limitation to using studio in a notebook is that variables being used
in a studio-run cell have to be pickleable. That means that, for example, you 
cannot use lambda functions defined elsewhere, because those are not 
pickleable. 


