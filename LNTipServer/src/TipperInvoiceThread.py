import binascii
import boto3
from CommonThread import CommonThread
import grpc
import hashlib
import json
import logging
import os
import traceback
from botocore.client import Config
from lnd import Client
from threading import Thread
from time import sleep
from SingleInvoiceListener import SingleInvoiceListener

class TipperInvoiceThread(CommonThread):
    def __init__(self, lnddatadir):
        super().__init__('TIThread', 'TipperInvoiceThread')
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.sfn = boto3.client('stepfunctions', config = config, region_name = 'us-west-2')
        self.lnd = Client(lnddatadir)

    def tryRun(self):
        super().tryRun()
        # Make sure lnd is active before getting a task
        self.lnd.getInfo()

        response = self.sfn.get_activity_task(
            activityArn = 'arn:aws:states:us-west-2:434623153115:activity:CdkStackgetTipperInvoiceActivity1238A05D',
            workerName = 'LNTipServer'
        )
        
        if 'taskToken' in response and 'input' in response:
            try:
                token = response['taskToken']
                data = json.loads(response['input'])

                self.logger.info(data)

                if data['type'] == 'HodlTip':
                    preimage = os.urandom(32)
                    hash = hashlib.sha256(preimage)
                    data['preimage'] = binascii.hexlify(preimage).decode()
                    data['hash'] = hash.hexdigest()
                    data['tipperInvoice'] = self.lnd.requestHoldInvoice(int(data['amount']), hash.digest(), 172800).payment_request
                    SingleInvoiceListener(preimage, hash.digest())
                else:
                    data['tipperInvoice'] = self.lnd.requestInvoice(int(data['amount']), data['id']).payment_request

                self.sfn.send_task_success(
                    taskToken = token,
                    output = json.dumps(data),
                )
            except Exception as e:
                self.logger.error('Payment failed with {} {}'.format(type(e), e))
                self.sfn.send_task_failure(
                    taskToken = token,
                    error = "Failed",
                    cause = str(e)
                )

            with self.cond:
                self.cond.wait(5)
