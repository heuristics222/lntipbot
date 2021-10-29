import boto3
from CommonThread import CommonThread
import grpc
import json
import os
from botocore.client import Config
from lnd import Client

class InvoiceSubscriptionThread(CommonThread):
    def __init__(self, datadir, lnddatadir):
        super().__init__('ISThread', 'InvoiceSubscriptionThread')
        self.lnd = Client(lnddatadir)
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.lamb = boto3.client('lambda', config = config, region_name = 'us-west-2')

        self.configPath = os.path.join(datadir, "config.json")

        if not os.path.isfile(self.configPath):
            self.logger.info('Invoice subscription configuration not found, recreating with settleIndex 0')
            json.dump({'settleIndex':0}, open(self.configPath, 'w'))

        self.config = json.load(open(self.configPath))

    def shutdown(self):
        super().shutdown()
        self.lnd.channel.close()

    def updateSettleIndex(self, index):
        self.config['settleIndex'] = index
        json.dump(self.config, open(self.configPath, 'w'))

    def tryRun(self):
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
                        FunctionName = 'arn:aws:lambda:us-west-2:434623153115:function:CdkStack-settledInvoiceHandler38092B08-4MojK9KjXaDx',
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
        except grpc._channel._Rendezvous as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                self.logger.info('Subscription interrupted')
                return

        with self.cond:
            self.cond.wait(1)
