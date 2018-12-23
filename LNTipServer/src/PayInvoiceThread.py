import boto3
import grpc
import json
import logging
import traceback
from botocore.client import Config
from lnd import Client
from threading import Thread
from time import sleep

class PayInvoiceThread(Thread):
    def __init__(self):
        super().__init__(name='PIThread')
        config = Config(read_timeout=65)
        self.sfn = boto3.client('stepfunctions', config = config, region_name = 'us-west-2')
        self.lnd = Client()
        self.logger = logging.getLogger(name='PayInvoiceThread')
        self.start()

    def handleError(self, token, errorMessage):
        self.sfn.send_task_failure(
            taskToken = token,
            error = "Failed",
            cause = str(errorMessage)
        )
        
    def handleTask(self, token, data):
        self.logger.info('Thread started for payment: {}'.format(data))
        paymentResponse = None
        for x in range(3):
            try:
                paymentResponse = self.lnd.sendPayment(data['invoice'])
                self.logger.info('paymentResponse: {}'.format(paymentResponse))
            except Exception as e:
                error = e
            else:
                if paymentResponse.payment_error:
                    error = paymentResponse.payment_error
                else:
                    data['paymentResponse'] = {
                        'payment_preimage': paymentResponse.payment_preimage.hex(),
                        'payment_route': str(paymentResponse.payment_route),
                    }
                    self.logger.info('Payment succeeded with {}'.format(paymentResponse.payment_preimage.hex()))
                    self.sfn.send_task_success(
                        taskToken = token,
                        output = json.dumps(data),
                    )
                    break
            self.logger.error('Payment failed with {} {}'.format(type(error), error))
        else:
            self.handleError(token, error)

    def run(self):
        self.logger.info('Starting Thread...')

        while True:
            try:
                # Make sure lnd is active before getting a task
                self.lnd.getInfo()

                response = self.sfn.get_activity_task(
                    activityArn = 'arn:aws:states:us-west-2:434623153115:activity:PayInvoice',
                    workerName = 'LNTipServer'
                )
                
                if 'taskToken' in response and 'input' in response:
                    token = response['taskToken']
                    data = json.loads(response['input'])

                    Thread(target = self.handleTask, args = (token, data)).start()

            except grpc._channel._Rendezvous as e:
                self.logger.error('LND appears to be down...')
                self.lnd = Client()
                sleep(60)

            except Exception as e:
                self.logger.error('Error type: {}'.format(type(e)))
                self.logger.info('{}\n\n{}'.format(e, traceback.format_exc()))
                sleep(60)
