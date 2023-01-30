import boto3
import json
import logging
import urllib3
from urllib.parse import quote
http = urllib3.PoolManager()

headers = {"User-Agent": "lntipbot/0.1 by lntipbot"}

WITHDRAW_FAILED_TEMPLATE = "https://oauth.reddit.com/api/comment?api_type=json&text=Your withdrawal failed with\n\n{}\n\nYour current balance is ⚡︎{} (satoshis).&thing_id={}"

DATA_TABLE = 'Data'
BALANCE_TABLE = 'Balance'

ddb = boto3.client('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore.vendored.requests').setLevel(logging.WARN)

def requestPost(url):
    response = http.request('POST', url, headers=headers)
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

    headers['Authorization'] = "bearer " + oauth['access_token']

def depositBalance(name, amount):
    response = ddb.update_item(
        TableName = BALANCE_TABLE,
        Key = {
            'User': {
                'S': name,
            }
        },
        UpdateExpression = 'SET Balance = Balance + :amount',
        ExpressionAttributeValues = {
            ':amount': {
                'N': str(amount)
            }
        },
        ReturnValues = 'UPDATED_NEW'
    )

    return int(response['Attributes']['Balance']['N'])

def payInvoiceFailed(event, context):
    uBalance = depositBalance(event['user'], event['amount'])
    balance = uBalance / 1000000.
    logger.info('Reimbursment succeeded.  New balance for {}: {} microsat'.format(event['user'], uBalance))

    getOAuthToken()

    if event['errorInfo'] and event['errorInfo']['Cause']:
        cause = event['errorInfo']['Cause']
    else:
        cause = "Unknown"

    cause = quote(cause)

    data = requestPost(WITHDRAW_FAILED_TEMPLATE.format(cause, balance, event['name']))
    logger.info(data)
