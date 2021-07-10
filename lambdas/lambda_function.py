import boto3
import json
import logging
import urllib3
http = urllib3.PoolManager()

from botocore.vendored import requests

S3_BUCKET = 'lntipbot'
CREDS_KEY = 'creds.json'

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ddb = boto3.client('dynamodb')
    
oauthResponse = ddb.get_item(
    TableName = 'Data',
    Key = {
        'Id': {
            'S': 'oauth',
        }
    }
)
oauth = json.loads(oauthResponse['Item']['Data']['S'])

headers = {
    'User-Agent': 'lntipbot/0.1 by lntipbot',
    'Authorization': 'bearer ' + oauth['access_token'],
}

def requestPost(url):
    return requests.post(url, headers=headers).json()
    
def requestGet(url):
    response = http.request('GET', url, headers=headers)
    if response.status == 503:
        logger.info(response.text)
        return False, {}
    elif response.status >= 300:
        logger.error(response.text)
        raise
    elif response.status == 200:
        return True, json.loads(response.data)
    else:
        return True, json.loads(response.data)
    
def getTotalBalances():
    response = ddb.scan(
        TableName = 'Balance',
        #Limit = 5
    )
    
    items = response['Items']
    
    sum = 0
    max = 0
    maxUser = ''
    
    for item in items:
        balance = int(item['Balance']['N'])
        user = item['User']['S']
        #print('{}:{}'.format(user, balance))
        sum = sum + balance
        if balance > max:
            maxUser = user
            max = balance

    print('Total: {}'.format(sum / 1000000))
    print('Max: {} with {}'.format(maxUser, max / 1000000))

def pretty_print_POST(req):
    """
    At this point it is completely built and ready
    to be fired; it is "prepared".

    However pay attention at the formatting used in 
    this function because it is programmed to be pretty 
    printed and may differ from the actual request.
    """
    print('{}\n{}\r\n{}\r\n\r\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\r\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))
    print()
    print()

def testOauth():
    s3 = boto3.client('s3')
    ddb = boto3.client('dynamodb')
    response = s3.get_object(
        Bucket=S3_BUCKET,
        Key=CREDS_KEY,
    )
    creds = json.loads(response['Body'].read())
    
    client_auth = requests.auth.HTTPBasicAuth(creds['appId'], creds['secret'])
    data = {"grant_type": "password", "username": creds['username'], "password": creds['password']}
    req = requests.Request('POST', "https://www.reddit.com/api/v1/access_token", auth=client_auth, data=json.dumps(data), headers={"User-Agent": "lntipbot/0.1 by lntipbot"})
    pretty_print_POST(req.prepare())
    
    headers = urllib3.util.make_headers(basic_auth='{}:{}'.format(creds['appId'], creds['secret']))
    headers["User-Agent"] = "lntipbot/0.1 by lntipbot"
    print(headers)
    print(json.dumps(data))
    response = http.request('POST', "https://www.reddit.com/api/v1/access_token", fields=data, headers=headers)

    oauthToken = json.loads(response.data)
    
    print(oauthToken)
    
    # response = ddb.put_item(
    #     TableName = 'Data',
    #     Item = {
    #         'Id': {
    #             'S': 'oauth'
    #         },
    #         'Data': {
    #             'S': json.dumps(oauthToken)
    #         },
    #     },
    # )
    
def testRequestGet():
    success, response = requestGet('https://oauth.reddit.com/me/m/tips/comments.json')
    #print(response)


def lambda_handler(event, context):
    testRequestGet()
    #testOauth()
    #response = http.request('GET', 'https://oauth.reddit.com/me/m/tips/comments.json', headers=headers)
    #requestPost("https://oauth.reddit.com/api/comment?api_type=json&text=darsh%26darsh" + "&thing_id=t1_ebjidln")
    #print(json.loads(response.data))
    
    #getTotalBalances()
    