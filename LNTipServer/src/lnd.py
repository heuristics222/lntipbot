import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
import invoices_pb2 as invoices
import invoices_pb2_grpc as invoicesrpc
import grpc
import os
import codecs


class Client:

    def __init__(self):
        os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'
        cert = open(os.path.expanduser('~/.lnd/tls.cert'), 'rb').read()
        certCredentials = grpc.ssl_channel_credentials(cert)
        authCredentials = grpc.metadata_call_credentials(self.metadataCallback)
        combinedCredentials = grpc.composite_channel_credentials(certCredentials, authCredentials)
        channel = grpc.secure_channel('localhost:10009', combinedCredentials)

        self.stub = lnrpc.LightningStub(channel)
        self.invoicesstub = invoicesrpc.InvoicesStub(channel)
        self.macaroon = codecs.encode(open(os.path.expanduser('~/.lnd/data/chain/bitcoin/mainnet/admin.macaroon'), 'rb').read(), 'hex')

    def metadataCallback(self, context, callback):
        callback([('macaroon', self.macaroon)], None)

    def requestInvoice(self, amount, tipId, expiry = 1200):
        request = ln.Invoice(
            memo = tipId,
            value = amount,
            expiry = expiry,
        )
        response = self.stub.AddInvoice(request)
        return response

    def requestHoldInvoice(self, amount, hash, expiry = 1200):
        request = invoices.AddHoldInvoiceRequest(
            memo = 'Test tip',
            value = amount,
            expiry = expiry,
            hash = hash
        )
        response = self.invoicesstub.AddHoldInvoice(request)
        return response

    def getInfo(self):
        request = ln.GetInfoRequest()
        response = self.stub.GetInfo(request)
        return response

    def subscribeSingleInvoice(self, hash):
        request = invoices.SubscribeSingleInvoiceRequest(
            r_hash = hash
        )
        return self.invoicesstub.SubscribeSingleInvoice(request)

    def subscribeInvoices(self, addIndex = 0, settleIndex = 0):
        request = ln.InvoiceSubscription(
            add_index = addIndex, 
            settle_index = settleIndex
        )
        return self.stub.SubscribeInvoices(request)

    def sendPayment(self, invoice, amt = None):
        if amt:
            if amt < 100000:
                feeLimit = 10
            elif amt < 200000:
                feeLimit = 20
            else:
                feeLimit = 25
            
            request = ln.SendRequest(
                payment_request=invoice,
                fee_limit=ln.FeeLimit(
                    fixed=feeLimit
                ),
                amt=amt
            )
        else:
            request = ln.SendRequest(
                payment_request=invoice,
                fee_limit=ln.FeeLimit(
                    fixed=10
                )
            )
        return self.stub.SendPaymentSync(request)
