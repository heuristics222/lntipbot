curl -o lightning.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/v0.17.3-beta/lnrpc/lightning.proto
curl -o invoices.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/v0.17.3-beta/lnrpc/invoicesrpc/invoices.proto

python -m grpc_tools.protoc --proto_path=/data/git/googleapis:. --mypy_out=. --python_out=. --grpc_python_out=. lightning.proto
python -m grpc_tools.protoc --proto_path=/data/git/googleapis:. --mypy_out=. --python_out=. --grpc_python_out=. invoices.proto

# cp ~/go12/src/github.com/lightningnetwork/lnd/lnrpc/rpc.proto .
#cp ~/go12/src/github.com/lightningnetwork/lnd/lnrpc/invoicesrpc/invoices.proto .
#python -m grpc_tools.protoc --proto_path=~/googleapis:. --python_out=. --grpc_python_out=. rpc.proto
#python -m grpc_tools.protoc --proto_path=~/googleapis:. --python_out=. --grpc_python_out=. invoices.proto
#cp * ~/vscode/lntipbot/LNTipServer/src/
