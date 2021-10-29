import boto3
from collections import OrderedDict
from CommonThread import CommonThread
import configparser
from botocore.client import Config
from datetime import datetime
from lnd import Client
import os
import requests

class MetricThread(CommonThread):
    def __init__(self, lnddatadir, btcdatadir):
        super().__init__('MetricThread', 'MetricThread')
        self.lnd = Client(lnddatadir)
        config = Config(
            read_timeout = 65,
            retries = dict(
                max_attempts = 10
            )
        )
        self.cw = boto3.client('cloudwatch', config = config, region_name = 'us-west-2')

        with open(os.path.join(btcdatadir, 'bitcoin.conf'), 'r') as f:
            configString = '[DEFAULT]\n' + f.read()
        self.btcConfig = configparser.ConfigParser(strict=False).read_string(configString)

    def isBtcUp(self):
        try:
            response = requests.post('http://{}:{}@127.0.0.1:{}'.format(self.btcConfig['rpcuser'], self.btcConfig['rpcpassword'], self.btcConfig['rpcport']),
                data={
                    'method': 'getnetworkinfo'
                }
            )
            return response.json()['result']['networkactive']
        finally:
            return False

    def isLndUp(self):
        try:
            self.lnd.getInfo()
            return True
        finally:
            return False

    def tryRun(self):
        if datetime.utcnow().minute == 0:
            self.logger.info('Sending status...')

        btcUp = self.isBtcUp()
        lndUp = self.isLndUp()

        self.cw.put_metric_data(
            Namespace='LNTipBot',
            MetricData=[
                {
                    'MetricName': 'LndUp',
                    'Timestamp': datetime.now(),
                    'Value': 1 if lndUp else 0,
                    'Unit': 'None',
                    'StorageResolution': 60
                },
                {
                    'MetricName': 'BtcUp',
                    'Timestamp': datetime.now(),
                    'Value': 1 if btcUp else 0,
                    'Unit': 'None',
                    'StorageResolution': 60
                }
            ]
        )
        self.throttle() 
