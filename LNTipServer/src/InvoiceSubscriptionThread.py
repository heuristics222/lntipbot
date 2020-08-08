import boto3
import grpc
import json
import logging
import os
import traceback
from botocore.client import Config
from lnd import Client
from threading import Thread
from time import sleep

class InvoiceSubscriptionThread(Thread):
    def __init__(self):
        super().__init__(name='ISThread')
        self.lnd = Client()
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.lamb = boto3.client('lambda', config = config, region_name = 'us-west-2')

        homedir = "{}/".format(os.path.expanduser("~"))
        directory = "{0}.{1}".format(homedir, "lntipbot")
        if not os.path.isdir(directory):
            os.mkdir(directory)

        self.configPath = os.path.join(directory, "config.json")

        if not os.path.isfile(self.configPath):
            json.dump({'settleIndex':11}, open(self.configPath, 'w'))

        self.config = json.load(open(self.configPath))
        self.logger = logging.getLogger(name='InvoiceSubscriptionThread')
        self.start()

    def updateSettleIndex(self, index):
        self.config['settleIndex'] = index
        json.dump(self.config, open(self.configPath, 'w'))

    def run(self):
        self.logger.info('Starting Thread...')

        while True:
            try:
                invoices = self.lnd.subscribeInvoices(settleIndex = self.config['settleIndex'])

                for invoice in invoices:
                    if invoice.settle_index > 0:
                        payload = {
                            'memo': invoice.memo,
                            'value': str(invoice.value),
                            'amt_paid': str(invoice.amt_paid * 1000)
                        }
                        self.logger.info(payload)
                        response = self.lamb.invoke(
                            FunctionName = 'arn:aws:lambda:us-west-2:434623153115:function:settledInvoiceHandler',
                            InvocationType = 'RequestResponse',
                            Payload = json.dumps(payload),
                        )
                        self.updateSettleIndex(invoice.settle_index)

                        if 'FunctionError' in response:
                            self.logger.error(response)
                    else:
                        self.logger.info({
                            'memo': invoice.memo,
                            'r_hash': invoice.r_hash
                        })

                sleep(1)

            except grpc._channel._Rendezvous as e:
                self.logger.error('LND appears to be down...')
                self.lnd = Client()
                sleep(60)

            except Exception as e:
                self.logger.error('Error type: {}'.format(type(e)))
                self.logger.info('{}\n\n{}'.format(e, traceback.format_exc()))
                sleep(60)
