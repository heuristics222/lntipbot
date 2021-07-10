import boto3
import json
import urllib3
http = urllib3.PoolManager()

def redditOAuthRequester(event, context):
    ddb = boto3.client('dynamodb')
    
    response = ddb.get_item(
        TableName = 'Data',
        Key = {
            'Id': {
                'S': 'creds',
            }
        }
    )
    creds = json.loads(response['Item']['Data']['S'])
    
    data = {"grant_type": "password", "username": creds['username'], "password": creds['password']}
    
    headers = urllib3.util.make_headers(basic_auth='{}:{}'.format(creds['appId'], creds['secret']))
    headers["User-Agent"] = "lntipbot/0.1 by lntipbot"
    response = http.request('POST', "https://www.reddit.com/api/v1/access_token", fields=data, headers=headers)

    oauthToken = json.loads(response.data)
    
    response = ddb.put_item(
        TableName = 'Data',
        Item = {
            'Id': {
                'S': 'oauth'
            },
            'Data': {
                'S': json.dumps(oauthToken)
            },
        },
    )
