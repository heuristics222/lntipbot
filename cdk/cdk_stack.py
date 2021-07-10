from aws_cdk import core as cdk
from aws_cdk import aws_apigateway as awsapigateway
from aws_cdk import aws_lambda as awslambda
from aws_cdk import aws_iam as iam
import subprocess

class CdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambdaRole = self.createLambdaRole()

        api = awsapigateway.RestApi(self, 'lntipbot')

        info = api.root.add_resource('info', default_integration=awsapigateway.MockIntegration(
            integration_responses=[
                awsapigateway.IntegrationResponse(
                    status_code='301',
                    response_parameters={
                        'method.response.header.Location': '\'https://www.reddit.com/r/LNTipBot2/wiki/index\'',
                        'method.response.header.Cache-Control': '\'max-age=300\''
                    }
                )
            ],
            request_templates={
                'application/json': '{"statusCode": 301}'
            }
        ))

        info.add_method('GET',
            method_responses=[{
                'statusCode': '301',
                'responseParameters': {
                    'method.response.header.Location': True,
                    'method.response.header.Cache-Control': True
                }
            }]
        )

        lambdaLayer = awslambda.LayerVersion(self, 'lambdaLayer', 
            code=awslambda.Code.from_asset(self.installRequirements('lambdas')),
            compatible_runtimes=[
                awslambda.Runtime.PYTHON_3_8
            ]
        )

        invoiceUriFunction = awslambda.Function(self, 'invoiceUriFunction', 
            code=awslambda.Code.from_asset('lambdas'),
            runtime=awslambda.Runtime.PYTHON_3_8,
            handler='getURI.getURI',
            role=lambdaRole,
            layers=[
                lambdaLayer
            ]
        )

        invoiceUri = api.root.add_resource('uri', default_integration=awsapigateway.LambdaIntegration(
            invoiceUriFunction
        ))

        invoiceUri.add_method('GET',
            
        )

    def installRequirements(self, path):
        outPath = f'{path}_deps'
        subprocess.check_call(f'pip install -r {path}/requirements.txt -t {outPath}'.split())
        return outPath

    def createLambdaRole(self):
        lambdaRole = iam.Role(self, 'lambdaRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            inline_policies={
                'DdbPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'dynamodb:PutItem',
                                'dynamodb:GetItem',
                                'dynamodb:UpdateItem'
                            ],
                            resources=[
                                # TODO: import to cdk
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Balance',
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Data',
                                'arn:aws:dynamodb:us-west-2:434623153115:table/Tips'
                            ]
                        )
                    ]
                ),
                'LogPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                'logs:CreateLogGroup',
                                'logs:CreateLogStream',
                                'logs:PutLogEvents'
                            ],
                            resources=[
                                'arn:aws:logs:*:*:*'
                            ]
                        )
                    ]
                )
            }
        )

        return lambdaRole