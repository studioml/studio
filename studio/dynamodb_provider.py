import logging
import boto3

from .nosql_provider import NoSQLProvider

logging.basicConfig()


class DynamoDBProvider(NoSQLProvider):
    def __init__(self, config, verbose=10):

        self.table_name = config['table']
        self.client = boto3.client('dynamodb')

        existing_tables = self.client.list_tables()
