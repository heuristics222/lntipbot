import boto3
import json
import logging
from urllib.parse import urlencode
import urllib3
http = urllib3.PoolManager()

headers = {
    'User-Agent': 'lntipbot/0.1 by lntipbot',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
}

DATA_TABLE = 'Data'

ddb = boto3.client('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore.vendored.requests').setLevel(logging.WARN)

def requestPost(url, body):
    response = http.request('POST', url,
        headers=headers,
        body=body
    )
    return json.loads(response.data)

def getOAuthToken():
    response = ddb.get_item(
        TableName = DATA_TABLE,
        Key = {
            'Id': {
                'S': 'oauth',
            }
        }
    )
    oauth = json.loads(response['Item']['Data']['S'])

    headers['Authorization'] = 'bearer ' + oauth['access_token']

def updateWiki(event, context):
    logger.info(event)

    subreddit = event['subreddit']
    page = event['page']

    getOAuthToken()

    logger.info(headers)

    path = 'resources/wiki/{subreddit}/{page}.md'.format(
        subreddit=subreddit,
        page=page
    )

    with open(path, 'r') as file:
        content = file.read()

        response = requestPost('https://oauth.reddit.com/r/{subreddit}/api/wiki/edit'.format(
            subreddit = subreddit
        ), urlencode({
            'content': content,
            'reason': '',
            'page': page
        }))

        logger.info(response)
