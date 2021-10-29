import boto3
from CommonThread import CommonThread
import json
from botocore.client import Config
from lnd import Client
from threading import Thread

class PayInvoiceThread(CommonThread):
    def __init__(self, lnddatadir):
        super().__init__('PIThread', 'PayInvoiceThread')
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.sfn = boto3.client('stepfunctions', config = config, region_name = 'us-west-2')
        self.lnd = Client(lnddatadir)

    def handleTaskError(self, token, errorMessage):
        self.sfn.send_task_failure(
            taskToken = token,
            error = "Failed",
            cause = str(errorMessage)
        )
        
    def handleTask(self, token, data):
        self.logger.info('Thread started for payment: {}'.format(data))
        paymentResponse = None
        for x in range(1):
            try:
                paymentResponse = self.lnd.sendPayment(data['invoice'], int(data['amount'] / 1000000))
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
            self.handleTaskError(token, error)

    def tryRun(self):
        # Make sure lnd is active before getting a task
        self.lnd.getInfo()

        response = self.sfn.get_activity_task(
            activityArn = 'arn:aws:states:us-west-2:434623153115:activity:CdkStackpayInvoiceActivityB30C5FBC',
            workerName = 'LNTipServer'
        )
        
        if 'taskToken' in response and 'input' in response:
            token = response['taskToken']
            data = json.loads(response['input'])

            # TODO: join all threads before exiting this one
            Thread(target = self.handleTask, args = (token, data)).start()

            with self.cond:
                self.cond.wait(10)
