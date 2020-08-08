cp ~/go12/src/github.com/lightningnetwork/lnd/lnrpc/rpc.proto .
cp ~/go12/src/github.com/lightningnetwork/lnd/lnrpc/invoicesrpc/invoices.proto .
python -m grpc_tools.protoc --proto_path=~/googleapis:. --python_out=. --grpc_python_out=. rpc.proto
python -m grpc_tools.protoc --proto_path=~/googleapis:. --python_out=. --grpc_python_out=. invoices.proto
cp * ~/vscode/lntipbot/LNTipServer/src/
