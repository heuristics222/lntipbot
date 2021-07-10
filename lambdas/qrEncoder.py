from io import BytesIO
import base64
import ddb.tips as tips
import logging
import os
import pyqrcode
import shutil
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def encodeInvoice(invoice):
    start = time.time()
    code = pyqrcode.create('lightning:' + invoice, error='L')
    logger.info('create: {}'.format(time.time() - start))
    start = time.time()
    file = BytesIO()
    code.svg(file, omithw=True)
    logger.info('svg: {}'.format(time.time() - start))

    encoded = base64.b64encode(file.getvalue()).decode()

    logger.info('encode: {}'.format(time.time() - start))

    return encoded

def qrEncoder(event, context):
    invoice = None
    logger.info(event)

    if 'queryStringParameters' in event and event['queryStringParameters'] != None and 'invoice' in event['queryStringParameters']:
        invoice = event['queryStringParameters']['invoice']
    elif 'queryStringParameters' in event and event['queryStringParameters'] != None and 'id' in event['queryStringParameters']:
        id = event['queryStringParameters']['id']
        tip = tips.get(id)
        if 'tipperInvoice' in tip:
            invoice = tip['tipperInvoice']
        else:
            logger.info('QR requested for tip with no invoice: {}'.format(id))
    else:
        logger.info('QR requested with no valid parameters')
    
    if invoice is not None:
        return {
            'isBase64Encoded': True,
            'headers': {
                'Content-Type': 'image/svg+xml'
            },
            'statusCode': 200,
            'body': encodeInvoice(invoice)
        }
    else:
        return {
            'isBase64Encoded': True,
            'headers': {},
            'statusCode': 400,
            'body': ''
        }
