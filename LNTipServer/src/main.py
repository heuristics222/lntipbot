import InvoiceSubscriptionThread
import PayInvoiceThread
import TipperInvoiceThread
import MetricThread

import logging
import os
import signal
import sys

RUNNING = True

def handleInterrupt(a, b):
    global RUNNING
    logger.info('Stopping lntipbot...')
    RUNNING = False

    metricThread.shutdown()
    getInvoiceThread.shutdown()
    invoiceSubThread.shutdown()
    payInvoiceThread.shutdown()


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logFormatter = logging.Formatter('%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s')

logHandler = logging.StreamHandler()
logHandler.setFormatter(logFormatter)
logger.addHandler(logHandler)

logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.WARN)

datadir = os.path.expanduser('~/.lntipbot')
if len(sys.argv) > 1:
    datadir = sys.argv[1]

if not os.path.exists(datadir):
    os.mkdir(datadir)

logFileHandler = logging.FileHandler(os.path.join(datadir, 'log.txt'))
logFileHandler.setFormatter(logFormatter)
logger.addHandler(logFileHandler)

lnddatadir = os.path.expanduser('~/.lnd')
if len(sys.argv) > 2:
    lnddatadir = sys.argv[2]

btcdatadir = os.path.expanduser('~/.bitcoin')
if len(sys.argv) > 3:
    btcdatadir = sys.argv[3]

if not os.path.exists(os.path.join(lnddatadir, 'tls.cert')):
    raise Exception('Cannot find lnd tls cert')

if not os.path.exists(os.path.join(lnddatadir, 'data/chain/bitcoin/mainnet/admin.macaroon')):
    raise Exception('Cannot find lnd admin macaroon')

if not os.path.exists(os.path.join(btcdatadir, 'bitcoin.conf')):
    raise Exception('Cannot find bitcoin.conf')

logger.info('Starting lntipbot...')

invoiceSubThread = InvoiceSubscriptionThread.InvoiceSubscriptionThread(datadir, lnddatadir).start()
payInvoiceThread = PayInvoiceThread.PayInvoiceThread(lnddatadir).start()
metricThread = MetricThread.MetricThread(lnddatadir, btcdatadir).start()
getInvoiceThread = TipperInvoiceThread.TipperInvoiceThread(lnddatadir).start()

signal.signal(signal.SIGINT, handleInterrupt)
signal.signal(signal.SIGTERM, handleInterrupt)

while RUNNING:
    signal.pause()

metricThread.join()
getInvoiceThread.join()
invoiceSubThread.join()
payInvoiceThread.join()

logger.info('Shutdown successful')
