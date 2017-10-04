import boto3

from .nosql_provider import NoSQLProvider


class DynamoDBProvider(NoSQLProvider):
    
    def __init__(self, config):

        self.experiments_table_name = config.get('experiments_table', 
                                                 'studioml_experiments')

        
        self.users_table_name = config.get('users_table',
                                           'studioml_users')

    
        self.projects_table_name = config.get('projects_table',  
                                              'studioml_projects')


        self.throughput = config.get('throughput', 
                                     {'read': 5, 'write': 5})

        
        self.client = boto3.client('dynamodb')

        self.tables = {
            'users': config.get('users_table', 'studioml_users'),
            'experiments': config.get('experiments_table', 'studioml_experiments'),
            'projects': config.get('projects_table', 'studioml_projects')
        }


        tables = self.client.list_tables()['TableNames']
        if not self.users_table_name in tables:
            resp = self.client.create_table(
                TableName=self.users_table_name,
                KeySchema = [
                    {
                        'AttributeName': 'user_id',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'email',
                        'KeyType': 'RANGE'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'user_id',
                        'AttributeType': 'S'
                    }, 
                    {
                        'AttributeName': 'email',
                        'AttributeType': 'S'
                    }
                ],

                ProvisionedThroughput={
                    'ReadCapacityUnits': self.throughput['read'],
                    'WriteCapacityUnits': self.throughput['write']
                }
            )


        if not self.experiments_table_name in tables:
            resp = self.client.create_table(
                TableName=self.experiments_table_name,
                KeySchema = [
                    {
                        'AttributeName': 'key',
                        'KeyType': 'HASH'
                    },
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'key',
                        'AttributeType': 'S'
                    }, 
                ],

                ProvisionedThroughput={
                    'ReadCapacityUnits': self.throughput['read'],
                    'WriteCapacityUnits': self.throughput['write']
                }
            )

        if not self.projects_table_name in tables:
            resp = self.client.create_table(
                TableName=self.projects_table_name,
                KeySchema = [
                    {
                        'AttributeName': 'key',
                        'KeyType': 'HASH'
                    },
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'key',
                        'AttributeType': 'S'
                    }, 
                ],

                ProvisionedThroughput={
                    'ReadCapacityUnits': self.throughput['read'],
                    'WriteCapacityUnits': self.throughput['write']
                }
            )


    def _get(self, key):
        split_key = key.split('/')
        table_name = split_key[0]
        
        if table_name not in self.tables.keys():
            raise ValueError('Invalid table: ' + table_name)
        
        dbresponse = self.client.get_item(
            TableName=self.tables[table_name],
            Key='/'.join(split_key[1:])
        )

        return dbrespons

    def _set(self, key, value):
        split_key = key.split('/')
        table_name = split_key[0]
        
        if table_name not in self.tables.keys():
            raise ValueError('Invalid table: ' + table_name)
        
        dbresponse = self.client.get_item(
            TableName=self.tables[table_name],
            Key='/'.join(split_key[1:])
        )

        return dbrespons
 

                
             


