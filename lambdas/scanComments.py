import boto3
import datetime
import json
import logging
import re
import time
import uuid
from botocore.vendored import requests
import urllib3
http = urllib3.PoolManager()

MULTI = 'tips'
TIP_TRIGGER = 'lntip'
TIP_TRIGGER_EXP = re.compile('!' + TIP_TRIGGER + '\s+<?([0-9]+)>?')
HODL_TRIGGER_EXP = re.compile('!hodltip\s+<?([0-9]+)>?')
WITHDRAW_TRIGGER = re.compile('!withdraw\s+<?(?:lightning\:)?(lnbc([0-9]+(?:m|u|n|p)?)1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]+)>?$')
WITHDRAW_ALL_TRIGGER = re.compile('!withdraw\s+<?(?:lightning\:)?(lnbc1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]+)>?$')
DEPOSIT_MATCH = re.compile('!deposit\s+<?([0-9]+)>?')
DELETED = '[deleted]'

MIN_TIP = 500
MAX_TIP = 250000

TIP_WORKFLOW_ARN = 'arn:aws:states:us-west-2:434623153115:stateMachine:TipWorkflow'
WITHDRAW_WORKFLOW_ARN = 'arn:aws:states:us-west-2:434623153115:stateMachine:WithdrawWorkflow'

INFO_LOCATION = 'https://xnf5cwpq73.execute-api.us-west-2.amazonaws.com/prod/info'

TIP_TEMPLATE = "Hi u/{tipper}, thanks for tipping u/{tippee} **{amount}** satoshis!\n***\n*[^(More info)]({info}) ^| [^(Balance)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=balance%26message=!balance) ^| [^(Deposit)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=deposit%26message=!deposit%2010000) ^| [^(Withdraw)](https://www.reddit.com/message/compose/?to=lntipbot%26subject=withdraw%26message=!withdraw%20put_invoice_here) ^| ^(Something wrong?  Have a question?) [^(Send me a message)](https://www.reddit.com/message/compose/?to=drmoore718)*"

DATA_TABLE = 'Data'
BALANCE_TABLE = 'Balance'
TIP_TABLE = 'Tips'

POLL_INTERVAL = 14
MAX_RUNTIME = 48

PM_MIN_TIP = 'https://oauth.reddit.com/api/compose?api_type=json&subject=Minimum tip&to={}&text=It looks like you tried to tip ⚡︎{} (satoshis), but the minimum tip amount is ⚡︎{}.'
PM_NO_COMMAND = 'https://oauth.reddit.com/api/comment?api_type=json&text=I didn\'t understand your command.  [More info]({info})&thing_id={thing}'
PM_BALANCE_REPLY = 'https://oauth.reddit.com/api/comment?api_type=json&text=Your balance is ⚡︎{} (satoshis)&thing_id={}'
PM_WITHDRAW_INSUFFICIENT_FUNDS_REPLY = 'https://oauth.reddit.com/api/comment?api_type=json&text=You didn\'t have enough funds.  Your balance is ⚡︎{} (satoshis)&thing_id={}'

PM_DOWN_TEMPORARILY_REPLY = 'https://oauth.reddit.com/api/comment?api_type=json&text=Deposits and withdrawals are down temporarily while my bitcoin node reindexes, sorry for the inconvenience [Status](https://www.reddit.com/r/lntipbot/wiki/index)&thing_id={}'

ddb = boto3.client('dynamodb')
sfn = boto3.client('stepfunctions')
headers = {
    'User-Agent': 'lntipbot/0.1 by lntipbot',
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore.vendored.requests').setLevel(logging.WARN)

def refreshOauthToken():
    oauthResponse = ddb.get_item(
        TableName = DATA_TABLE,
        Key = {
            'Id': {
                'S': 'oauth',
            }
        }
    )
    oauth = json.loads(oauthResponse['Item']['Data']['S'])

    headers['Authorization'] = 'bearer ' + oauth['access_token']

refreshOauthToken()

def startInvoiceWorkflow(tip):
    response = sfn.start_execution(
        stateMachineArn = TIP_WORKFLOW_ARN,
        name = tip['id'],
        input = json.dumps(tip),
    )

def startWithdrawWorkflow(invoice, amount, user, name):
    response = sfn.start_execution(
        stateMachineArn = WITHDRAW_WORKFLOW_ARN,
        name = uuid.uuid4().hex,
        input = json.dumps({
            'invoice': invoice,
            'amount': amount,
            'user': user,
            'name': name,
        })
    )


def requestGet(url):
    response = http.request('GET', url, headers=headers)
    if response.status == 503:
        logger.info(response.text)
        return False, {}
    elif response.status >= 300:
        logger.error(response.text)
        raise
    else:
        return True, json.loads(response.data)

def requestPost(url):
    response = http.request('POST', url, headers=headers)
    return json.loads(response.data)

def getNotificationString(tipdata):
    return TIP_TEMPLATE.format(
        tipper = tipdata['tipper'],
        tippee = tipdata['tippee'],
        amount = tipdata['amount'],
        info = INFO_LOCATION
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

def handleTip(comment, amount, hodlTip):
    tipdata = {}
    tipdata['amount'] = amount
    tipdata['tipper'] = comment['data']['author']
    tipdata['tippee'] = comment['data']['link_author']
    tipdata['id'] = uuid.uuid4().hex
    tipdata['type'] = 'HodlTip' if hodlTip else 'Tip'
    tipdata['resourceId'] = comment['data']['name']
    tipdata['parentResourceId'] = comment['data']['parent_id']
    tipdata['time'] = datetime.datetime.fromtimestamp(comment['data']['created_utc']).strftime('%Y-%m-%d %H:%M:%S')

    # Parent is a comment, need to get the parent comment to get the author
    if comment['data']['parent_id'].startswith('t1'):
        success, data = requestGet('https://oauth.reddit.com/api/info.json?id=' + comment['data']['parent_id'])
        tipdata['tippee'] = data['data']['children'][0]['data']['author']

    if tipdata['tipper'] == DELETED:
        logger.info('Tipper was deleted')
        return
    if tipdata['tippee'] == DELETED:
        logger.info('Tippee was deleted')
        return
    if tipdata['tipper'] == tipdata['tippee']:
        logger.info('Tipper was the same as tippee: {}'.format(tipdata['tipper']))
        return

    tipAmount = int(tipdata['amount'])
    if tipAmount < MIN_TIP:
        logger.info('Tip was too small: ⚡︎{} (satoshis)'.format(tipAmount))
        try:
            requestPost(PM_MIN_TIP.format(tipdata['tipper'], tipAmount, MIN_TIP))
        except:
            pass
        return
    elif tipAmount > MAX_TIP:
        logger.info('Tip was too large: ⚡︎{} (satoshis)'.format(tipAmount))
        return

    if hodlTip:
        logger.info('Handling a hodl tip')
        startInvoiceWorkflow(tipdata)
        pass
    else:
        tipAmount = tipAmount * 1000000
        try:
            withdrawBalance(tipdata['tipper'], tipAmount)
        except Exception as e:
            logger.info('Couldn\'t transfer balance, sending invoice {}'.format(type(e)))
            startInvoiceWorkflow(tipdata)
        else:
            depositBalance(tipdata['tippee'], tipAmount)
            data = requestPost("https://oauth.reddit.com/api/comment?api_type=json&text=" + getNotificationString(tipdata) + "&thing_id=" + tipdata['resourceId'])
            logger.info(data)
            saveTip(tipdata)


def handleComment(comment):
    commentBody = comment['data']['body'].lower()
    match = TIP_TRIGGER_EXP.search(commentBody)
    hodlmatch = HODL_TRIGGER_EXP.search(commentBody)

    logger.info('Handling comment {}'.format(comment['data']['name']))
    #logger.info('Comment body: {}'.format(commentBody))
    #logger.info('Comment body type: {}'.format(type(commentBody)))

    if match:
        handleTip(comment, match.group(1), False)
    elif hodlmatch:
        handleTip(comment, hodlmatch.group(1), True)

def invoiceAmtToMicrosat(amt):
    if amt[-1] == 'm':
        return int(amt[:-1]) * 100000000000
    elif amt[-1] == 'u':
        return int(amt[:-1]) * 100000000
    elif amt[-1] == 'n':
        return int(amt[:-1]) * 100000
    elif amt[-1] == 'p':
        return int(amt[:-1]) * 100
    else:
        return int(amt) * 100000000000000

def withdraw(withdrawer, withdrawMicrosat, messageId, invoice):
    logging.info('{} attempting to withdraw {} microsat'.format(withdrawer, withdrawMicrosat))

    try:
        newBal = withdrawBalance(withdrawer, withdrawMicrosat)
    except ddb.exceptions.ConditionalCheckFailedException as e:
        balance = getBalance(withdrawer)

        logger.info('Not enough funds.  Tried to withdraw {} microsat but had {} microsat'.format(withdrawMicrosat, balance))
        logger.info(e)

        requestPost(PM_WITHDRAW_INSUFFICIENT_FUNDS_REPLY.format(balance/1000000., messageId))
    else:
        logger.info('Withdrawal succeeded.  New balance {} microsat'.format(newBal))
        startWithdrawWorkflow(invoice, withdrawMicrosat, withdrawer, messageId)

def handleMessage(message):
    messageBody = message['data']['body'].strip().lower()
    withdrawMatch = WITHDRAW_TRIGGER.match(messageBody)
    withdrawAllMatch = WITHDRAW_ALL_TRIGGER.match(messageBody)
    depositMatch = DEPOSIT_MATCH.match(messageBody)

    logger.info('Handling message {}'.format(message['data']['name']))
    #logger.info('Message body: {}'.format(messageBody))

    # Don't handle t1's as messages (public comments)
    if message['data']['name'].startswith('t1'):
        return

    if messageBody == '!balance':
        balance = getBalance(message['data']['author'])

        requestPost(PM_BALANCE_REPLY.format(balance/1000000., message['data']['name']))
    elif withdrawMatch:
        #url = PM_DOWN_TEMPORARILY_REPLY.format(message['data']['name'])
        #logger.info(url)
        #result = requestPost(url)
        #logger.info(result)
        #return

        withdraw(message['data']['author'], invoiceAmtToMicrosat(withdrawMatch.group(2)), message['data']['name'], withdrawMatch.group(1))

    elif withdrawAllMatch:
        #url = PM_DOWN_TEMPORARILY_REPLY.format(message['data']['name'])
        #logger.info(url)
        #result = requestPost(url)
        #logger.info(result)
        #return

        withdraw(message['data']['author'], getBalance(message['data']['author']), message['data']['name'], withdrawAllMatch.group(1))

    elif depositMatch:
        #url = PM_DOWN_TEMPORARILY_REPLY.format(message['data']['name'])
        #logger.info(url)
        #result = requestPost(url)
        #logger.info(result)
        #return

        tipdata = {}
        tipdata['amount'] = depositMatch.group(1)
        tipdata['tippee'] = message['data']['author']
        tipdata['tipper'] = message['data']['author']
        tipdata['id'] = uuid.uuid4().hex
        tipdata['type'] = 'Deposit'
        tipdata['resourceId'] = message['data']['name']
        tipdata['time'] = datetime.datetime.fromtimestamp(message['data']['created_utc']).strftime('%Y-%m-%d %H:%M:%S')

        if int(tipdata['amount']) > 0:
            logger.info('Starting deposit invoice workflow for ⚡︎{} (satoshis) for {}'.format(tipdata['amount'], tipdata['tippee']))
            startInvoiceWorkflow(tipdata)
        else:
            logger.info('Got a 0 amount deposit')
    else:
        url = PM_NO_COMMAND.format(
            thing = message['data']['name'],
            info = INFO_LOCATION
        )
        logger.info(url)
        result = requestPost(url)
        logger.info(result)


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

def withdrawBalance(name, amount):
    response = ddb.update_item(
        TableName = BALANCE_TABLE,
        Key = {
            'User': {
                'S': name,
            }
        },
        UpdateExpression = 'SET Balance = Balance - :amount',
        ConditionExpression = 'Balance >= :amount',
        ExpressionAttributeValues = {
            ':amount': {
                'N': str(amount)
            }
        },
        ReturnValues = 'UPDATED_NEW'
    )

    logger.info('{} withdraw {}'.format(name, response))

    return int(response['Attributes']['Balance']['N'])

def depositBalance(name, amount):
    response = ddb.update_item(
        TableName = BALANCE_TABLE,
        Key = {
            'User': {
                'S': name,
            }
        },
        UpdateExpression = 'ADD Balance :q',
        ExpressionAttributeValues = {
            ':q': {
                'N': str(amount)
            }
        },
        ReturnValues = 'UPDATED_NEW'
    )

    logger.info('{} deposit {}'.format(name, response))

    if 'Item' in response:
        return int(response['Item']['Balance']['N'])
    else:
        return 0

def getData(dataId):
    response = ddb.get_item(
        TableName = DATA_TABLE,
        Key = {
            'Id': {
                'S': dataId,
            }
        },
        ConsistentRead = True
    )
    return response

def saveData(dataId, data):
    response = ddb.put_item(
        TableName = DATA_TABLE,
        Item = {
            'Id': {
                'S': dataId
            },
            'Data': {
                'S': json.dumps({
                    'data': {
                        'name': data['data']['name'],
                        'created_utc': data['data']['created_utc']
                    }

                })
            },
        },
    )

def scannerLoop(event, context):
    logger.info('Starting reddit scanner {}'.format(event))
    global TIP_WORKFLOW_ARN
    global WITHDRAW_WORKFLOW_ARN
    TIP_WORKFLOW_ARN = event['tipWorkflowArn']
    WITHDRAW_WORKFLOW_ARN = event['withdrawWorkflowArn']

    refreshOauthToken()

    startTime = time.perf_counter()

    while True:
        scanComments()
        scanMessages()

        if time.perf_counter() - startTime > MAX_RUNTIME - POLL_INTERVAL:
            break
        time.sleep(POLL_INTERVAL)

def idAsInt(id):
    return int(id.split('_')[1], 36)

def scan(requestUrl, dataId, filter, handler):
    lastData = getData(dataId)
    hasLastData = 'Item' in lastData

    if hasLastData:
        lastData = json.loads(lastData['Item']['Data']['S'])

    success, requestData = requestGet(requestUrl)

    if not success:
        return

    if 'data' not in requestData:
        logger.error('Request failed: {} {}'.format(requestUrl, requestData))
        raise Exception('Reddit query failed')

    dataElements = [a for a in requestData['data']['children'] if a['kind'] == filter]

    if len(dataElements) == 0:
        return

    names = [a['data']['name'] for a in dataElements]
    logger.info(str(names))

    if hasLastData:
        for data in reversed(dataElements):
            if idAsInt(data['data']['name']) > idAsInt(lastData['data']['name']):
                try:
                    handler(data)
                except Exception as e:
                    logger.exception('Failed to parse {} {}'.format(data['data']['name'], e))

        if idAsInt(dataElements[0]['data']['name']) > idAsInt(lastData['data']['name']):
            saveData(dataId, dataElements[0])

    else:
        # Marks the first data as the last one parsed in the case that the
        # function is running for the first time.
        saveData(dataId, dataElements[0])

def scanMessages(event={}, context={}):
    logger.info('Scanning messages')
    scan(
        'https://oauth.reddit.com/message/inbox.json',
        'lastMessage',
        't4',
        handleMessage
    )

def scanComments(event={}, context={}):
    logger.info('Scanning comments')
    scan(
        'https://oauth.reddit.com/me/m/' + MULTI + '/comments.json',
        'lastComment',
        't1',
        handleComment
    )
