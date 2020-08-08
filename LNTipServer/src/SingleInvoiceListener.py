import binascii
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

class SingleInvoiceListener(Thread):
    def __init__(self, preimage, hash):
        super().__init__()
        self.lnd = Client()
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.lamb = boto3.client('lambda', config = config, region_name = 'us-west-2')
        self.hash = hash
        self.preimage = preimage

        self.logger = logging.getLogger(name='SingleInvoiceListener')
        self.start()

    def run(self):
        self.logger.info('Starting Thread...')

        while True:
            try:
                self.logger.info('Listening for ' + binascii.hexlify(self.hash).decode())
                invoices = self.lnd.subscribeSingleInvoice(self.hash)

                for invoice in invoices:
                    self.logger.info(str(invoice))
                    self.logger.info({
                        'memo': invoice.memo,
                        'r_hash': binascii.hexlify(invoice.r_hash).decode()
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
