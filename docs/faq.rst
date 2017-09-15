Frequently Asked Questions
==========================

1. Is it possible to view the experiment artifacts outside of the Web UI?

Yes! 
   ::
       
       from studio import model
       with model.get_db_provider() as db:
           experiment = db.get_experiment(<experiment_key>)


will return an experiment object that contains all the information about the experiment with key ``<experiment key>``.
