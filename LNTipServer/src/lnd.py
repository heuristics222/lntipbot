import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
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

    def getInfo(self):
        request = ln.GetInfoRequest()
        response = self.stub.GetInfo(request)
        return response

    def subscribeInvoices(self, addIndex = 0, settleIndex = 0):
        request = ln.InvoiceSubscription(
            add_index = addIndex, 
            settle_index = settleIndex
        )
        return self.stub.SubscribeInvoices(request)

    def sendPayment(self, invoice, amt = None):
        if amt:
            if amt < 90000:
                feeLimit = 10
            else:
                feeLimit = 15
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
