import boto3
import json
import logging
import urllib3
http = urllib3.PoolManager()

headers = {"User-Agent": "lntipbot/0.1 by lntipbot"}

WITHDRAW_SUCCEEDED_TEMPLATE = "https://oauth.reddit.com/api/comment?api_type=json&text=Withdrawal of ⚡︎{} (satoshis) successful!\n\nPayment preimage: {}\n\nYour current balance is ⚡︎{}.&thing_id={}"

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

def getBalance(name):
    response = ddb.get_item(
        TableName = BALANCE_TABLE,
        Key = {
            'User': {
                'S': name,
            }
        }
    )

    if 'Item' in response:
        return int(response['Item']['Balance']['N'])
    else:
        return 0

def payInvoiceSucceeded(event, context):
    uBalance = getBalance(event['user'])
    balance = uBalance / 1000000.
    logger.info('Withdrawal successful.  New balance for {}: {} microsat'.format(event['user'], uBalance))

    getOAuthToken()

    data = requestPost(WITHDRAW_SUCCEEDED_TEMPLATE.format(event['amount'] / 1000000., event['paymentResponse']['payment_preimage'], balance, event['name']))
    logger.info(data)
