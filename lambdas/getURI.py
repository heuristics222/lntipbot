import boto3
import logging
import ddb.tips as tips

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PAGE_TEMPLATE = (
'<html style="font: normal large verdana,arial,helvetica,sans-serif; background-color: #303030">'
    '<head>'
        '<meta charset="UTF-8">'
        '<meta name="google" content="notranslate">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>'
            'lntipbot invoice URI'
        '</title>'
    '</head>'
    '<body style="margin: 0px;">'
        '<style>'
            'a:link {{color: #D4D4D4;}} a:visited {{color: #D4D4D4;}} a:hover {{color: #D4D4D4;}} a:active {{color: #D4D4D4;}}'
        '</style>'
        '<div style="padding: 8px;">'
            '<a style="word-break: break-all;" href="lightning:{invoice}">'
                '{invoice}'
            '</a>'
        '</div>'
    '</body>'
'</html>'
)

def getURI(event, context):
    logger.info(event)

    if 'queryStringParameters' in event and event['queryStringParameters'] != None and 'id' in event['queryStringParameters']:
        id = event['queryStringParameters']['id']
        tip = tips.get(id)

        if 'tipperInvoice' in tip:
            invoice = tip['tipperInvoice']
            return {
                'isBase64Encoded': False,
                'headers': {
                    'Content-Type': 'text/html'
                },
                'statusCode': 200,
                'body': PAGE_TEMPLATE.format(invoice=invoice)
            }
        else:
            logger.info('URI requested for tip with no invoice: {}'.format(id))
    else:
        logger.info('Missing id query parameter')
    
    return {
        'isBase64Encoded': False,
        'headers': {
        },
        'statusCode': 400,
        'body': ''
    }