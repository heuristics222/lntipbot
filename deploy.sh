#!/bin/bash

if ! [ -x "$(command -v sam)" ]; then
    CMD='sam.cmd'
else
    CMD='sam'
fi

$CMD build -b build

$CMD deploy --profile $1 --region us-west-2 --template-file build/template.yaml --stack-name TipbotStack --capabilities CAPABILITY_IAM --s3-bucket tipbot-deployment-bucket
