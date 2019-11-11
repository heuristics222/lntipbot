import InvoiceSubscriptionThread
import PayInvoiceThread
import TipperInvoiceThread

import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logFormatter = logging.Formatter('%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s')

logHandler = logging.StreamHandler()
logHandler.setFormatter(logFormatter)
logger.addHandler(logHandler)

logFileHandler = logging.FileHandler(os.path.expanduser('~/.lntipbot/log.txt'))
logFileHandler.setFormatter(logFormatter)
logger.addHandler(logFileHandler)

logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.WARN)



getInvoiceThread = TipperInvoiceThread.TipperInvoiceThread()
invoiceSubThread = InvoiceSubscriptionThread.InvoiceSubscriptionThread()
payInvoiceThread = PayInvoiceThread.PayInvoiceThread()
getInvoiceThread.join()
invoiceSubThread.join()
payInvoiceThread.join()
