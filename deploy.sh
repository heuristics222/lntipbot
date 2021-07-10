#!/bin/bash

if ! [ -x "$(command -v sam)" ]; then
    CMD='sam.cmd'
else
    CMD='sam'
fi

$CMD build -b build

$CMD deploy --profile dev --region us-west-2 --template-file build/template.yaml --stack-name TipbotStack --capabilities CAPABILITY_IAM --s3-bucket tipbot-deployment-bucket

#aws cloudformation package --profile dev --template-file build/template.yaml --s3-bucket tipbot-deployment-bucket --output-template-file build/deployTemplate.yaml

#aws cloudformation deploy --profile dev --template-file build/deployTemplate.yaml --stack-name TipbotStack --capabilities CAPABILITY_IAM
