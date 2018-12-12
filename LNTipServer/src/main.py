import InvoiceSubscriptionThread
import PayInvoiceThread
import TipperInvoiceThread

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
logFormatter = logging.Formatter('%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s')
logHandler.setFormatter(logFormatter)
logger.addHandler(logHandler)
logging.getLogger('botocore.vendored.requests.packages.urllib3.connectionpool').setLevel(logging.WARN)



getInvoiceThread = TipperInvoiceThread.TipperInvoiceThread()
invoiceSubThread = InvoiceSubscriptionThread.InvoiceSubscriptionThread()
payInvoiceThread = PayInvoiceThread.PayInvoiceThread()
getInvoiceThread.join()
invoiceSubThread.join()
payInvoiceThread.join()
