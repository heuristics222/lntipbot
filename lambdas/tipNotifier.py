import json
import boto3
import urllib3
http = urllib3.PoolManager()

headers = {"User-Agent": "lntipbot/0.1 by lntipbot"}

# TODO: get endpoint from cdk?
ENDPOINT = 'https://xnf5cwpq73.execute-api.us-west-2.amazonaws.com/prod/'

HODL_TEMPLATE = 'Hi u/{tipper}, thanks for tipping u/{tippee} **{amount}** satoshis!\n\nPlease pay the following invoice [[QR]({endpoint}qr?id={id} "Generate QR") / [URI]({endpoint}/uri?id={id} "Generate URI")] and your payment will be held for up to one day or until the tip is claimed.\n***\n>!{invoice}!<\n***\n*[^(More info)](https://xnf5cwpq73.execute-api.us-west-2.amazonaws.com/prod/info) ^| [^(Balance)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=balance%26message=!balance) ^| [^(Deposit)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=deposit%26message=!deposit%2010000) ^| [^(Withdraw)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=withdraw%26message=!withdraw%20put_invoice_here) ^| ^(Something wrong?  Have a question?) [^(Send me a message)](https://www.reddit.com/message/compose/?to=drmoore718)*'
TIP_TEMPLATE = 'Hi u/{tipper}, thanks for tipping u/{tippee} **{amount}** satoshis!\n\nYou didn\'t have enough balance, you can pay the following invoice [[QR]({endpoint}qr?id={id} "Generate QR") / [URI]({endpoint}/uri?id={id} "Generate URI")] instead.\n***\n>!{invoice}!<\n***\n*[^(More info)](https://xnf5cwpq73.execute-api.us-west-2.amazonaws.com/prod/info) ^| [^(Balance)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=balance%26message=!balance) ^| [^(Deposit)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=deposit%26message=!deposit%2010000) ^| [^(Withdraw)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=withdraw%26message=!withdraw%20put_invoice_here) ^| ^(Something wrong?  Have a question?) [^(Send me a message)](https://www.reddit.com/message/compose/?to=drmoore718)*'
DEPOSIT_TEMPLATE = 'Hi u/{tippee}, thanks for depositing **{amount}** satoshis!\n\nPlease pay the following invoice [[QR]({endpoint}qr?id={id} "Generate QR") / [URI]({endpoint}/uri?id={id} "Generate URI")] to have the funds credited to your balance.\n***\n{invoice}\n***\nHappy tipping!'

DATA_TABLE = 'Data'
TIP_TABLE = 'Tips'

ddb = boto3.client('dynamodb')

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

def getNotificationString(event):
    if event['type'] == 'Tip':
        return TIP_TEMPLATE.format(
            tipper = event['tipper'],
            tippee = event['tippee'],
            amount = event['amount'],
            invoice = event['tipperInvoice'],
            endpoint = ENDPOINT,
            id = event['id']
        )
    elif event['type'] == 'Deposit':
        return DEPOSIT_TEMPLATE.format(
            tippee = event['tippee'],
            amount = event['amount'],
            invoice = event['tipperInvoice'],
            endpoint = ENDPOINT,
            id = event['id']
        )
    elif event['type'] == 'HodlTip':
        return HODL_TEMPLATE.format(
            tipper = event['tipper'],
            tippee = event['tippee'],
            amount = event['amount'],
            invoice = event['tipperInvoice'],
            endpoint = ENDPOINT,
            id = event['id']
        )
    
def saveTip(data):
    response = ddb.put_item(
        TableName = TIP_TABLE,
        Item = {
            'Id': {
                'S': data['id']
            },
            'Data': {
                'S': json.dumps(data)
            },
            'Tipper': {
                'S': data['tipper']
            },
            'Tippee': {
                'S': data['tippee']
            },
            'Amount': {
                'N': data['amount']
            },
            'Time': {
                'S': data['time']
            },
            'Type': {
                'S': data['type']
            },
        },
    )

def tipNotifier(event, context):
    getOAuthToken()
    print(event)
    data = requestPost("https://oauth.reddit.com/api/comment?api_type=json&text=" + getNotificationString(event) + "&thing_id=" + event['resourceId'])
    print(data)
    event['notificationId'] = data['json']['data']['things'][0]['data']['name']
    
    saveTip(event)
