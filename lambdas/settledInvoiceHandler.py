import boto3
import json
import logging
import urllib3
http = urllib3.PoolManager()

headers = {"User-Agent": "lntipbot/0.1 by lntipbot"}

TIP_TEMPLATE = "Hi u/{tipper}, thanks for tipping u/{tippee} **{amount}** satoshis!\n\n^(edit: Invoice paid successfully!)\n\n***\n*[^(More info)](https://xnf5cwpq73.execute-api.us-west-2.amazonaws.com/prod/info) ^| [^(Balance)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=balance%26message=!balance) ^| [^(Deposit)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=deposit%26message=!deposit%2010000) ^| [^(Withdraw)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=withdraw%26message=!withdraw%20put_invoice_here) ^| ^(Something wrong?  Have a question?) [^(Send me a message)](https://www.reddit.com/message/compose/?to=drmoore718)*"
DEPOSIT_RECEIVED_TEMPLATE = "https://oauth.reddit.com/api/comment?api_type=json&text=Your deposit was received.  Your new balance is {} satoshis.&thing_id={}"

DATA_TABLE = 'Data'
TIP_TABLE = 'Tips'
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
    
def getInvoice(event):
    response = ddb.get_item(
        TableName = TIP_TABLE,
        Key = {
            'Id': {
                'S': event['memo'],
            }
        }
    )
    
    if 'Item' in response:
        return json.loads(response['Item']['Data']['S'])
        
def getNotificationString(settlement):
    return TIP_TEMPLATE.format(
        tipper = settlement['tipper'],
        tippee = settlement['tippee'],
        amount = settlement['amount']
    )

def settledInvoiceHandler(event, context):
    
    logger.info(event)
    
    if event['memo'] == '':
        return
    
    settlement = getInvoice(event)
    
    logger.info(settlement)
    
    if settlement:
        response = ddb.update_item(
            TableName = BALANCE_TABLE,
            Key = {
                'User': {
                    'S': settlement['tippee'],
                }
            },
            UpdateExpression = 'ADD Balance :q',
            ExpressionAttributeValues = {
                ':q': {
                    'N': event['amt_paid']
                }
            },
            ReturnValues = 'UPDATED_NEW'
        )
        
        uBalance = int(response['Attributes']['Balance']['N'])
        balance = uBalance / 1000000.
        
        logger.info('{} microsat added for {}.  New balance {} microsat'.format(event['amt_paid'], settlement['tippee'], uBalance))
        
        getOAuthToken()
        
        if settlement['type'] == 'Deposit':
            data = requestPost(DEPOSIT_RECEIVED_TEMPLATE.format(balance, settlement['resourceId']))
            logger.info(data)
        elif settlement['type'] == 'Tip':
            notificationId = settlement['notificationId']
            data = requestPost("https://oauth.reddit.com/api/editusertext?api_type=json&text=" + getNotificationString(settlement) + "&thing_id=" + notificationId)
            logger.info(data)
            
            
    else:
        logger.info('No invoice found for {}'.format(event['memo']))
