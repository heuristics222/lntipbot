import boto3
import json

TABLE_NAME = 'Tips'

ddb = boto3.client('dynamodb')

def get(id):
    response = ddb.get_item(
        TableName = TABLE_NAME,
        Key = {
            'Id': {
                'S': id,
            }
        }
    )
    
    if 'Item' in response:
        return json.loads(response['Item']['Data']['S'])
    else:
        return {}